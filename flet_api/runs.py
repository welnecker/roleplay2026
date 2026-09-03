from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote

from narrative_v2.repository import RuntimeConflictError
from packages.models import InstalledStoryPackage
from persistence.factory import build_google_sheets_repository
from persistence.models import utc_now_iso
from platform_core.auth import AuthenticatedUser
from roleplay.openrouter import generate_response
from roleplay.models import StoryState
from services import novel_frame_patch
from services.editorial_content import load_editorial_package, require_editorial_package
from services.editorial_diagnostics import log_editorial_exception
from services.editorial_scene_images import (
    resolve_editorial_scene_image,
    resolve_narrative_image_id,
    resolve_numbered_beat_image,
)
from services.immersive_onboarding import (
    build_immersive_context,
    identity_is_complete,
    persistent_profile_payload,
    recover_persistent_profile,
)
from services.novel_frame_output_contract import (
    FrameOutputContractError,
    enforce_frame_output_contract,
    frame_generation_instruction,
)
from services.novel_frame_reveal import frame_entry_count, frame_id
from services.novel_frame_runtime_support import (
    build_runtime_prompt,
    first_frame_movement,
    is_frame_script,
)
from services.novel_frame_images import image_sequence_for_frame
from services.novel_v2_adapter import movement_from_script, next_movement_id
from services.runtime_persistence import (
    RuntimePersistenceContext,
    open_persistent_runtime,
    persist_assistant_message,
)
from services.paid_run_access import clear_paid_access_cache
from services.story_profile import personalize_editorial_script


@dataclass(frozen=True, slots=True)
class RunFrame:
    run_id: str
    package_id: str
    frame_id: str
    content: str
    image_url: str
    revealed_entries: int
    entry_count: int
    entry_image_urls: tuple[str, ...] = ()
    finished: bool = False


@dataclass(frozen=True, slots=True)
class RunProfile:
    completed: bool
    preferred_name: str
    story_gender: str


def _is_idempotent_duplicate_advance(
    script: Any,
    *,
    expected_frame_id: str,
    current_movement_id: str,
) -> bool:
    return bool(
        expected_frame_id
        and current_movement_id
        and next_movement_id(script, expected_frame_id) == current_movement_id
    )


class FletRunService:
    """Fachada sem Streamlit para o runtime e a persistência autoritativos."""

    def __init__(self, secrets: dict[str, Any]) -> None:
        self.secrets = secrets
        self.repository = build_google_sheets_repository(secrets)
        if self.repository is None:
            raise ValueError("Google Sheets não está configurado para o runtime.")
        self.api_key = str(secrets.get("OPENROUTER_API_KEY", "") or "").strip()
        self.model = str(
            secrets.get("OPENROUTER_MODEL", "google/gemini-3-flash-preview")
            or "google/gemini-3-flash-preview"
        ).strip()
        self._locks: dict[tuple[str, str], Lock] = {}
        self._locks_guard = Lock()

    def _lock(self, user_id: str, package_id: str) -> Lock:
        key = (user_id, package_id)
        with self._locks_guard:
            return self._locks.setdefault(key, Lock())

    @staticmethod
    def _user(account: Any) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=account.user_id,
            email=account.email,
            display_name=account.display_name,
        )

    @staticmethod
    def _character(package: InstalledStoryPackage) -> tuple[str, str]:
        profile = package.manifest.card.character_profile
        name = profile.name if profile else package.manifest.card.title
        return name, name.strip().casefold().replace(" ", "_") or "character"

    @staticmethod
    def _current(messages: list[dict[str, object]]) -> dict[str, object] | None:
        return next(
            (
                item
                for item in reversed(messages)
                if str(item.get("role", "")) == "assistant"
                and str(item.get("content", "") or "").strip()
            ),
            None,
        )

    @staticmethod
    def _movement_id(message: dict[str, object] | None) -> str:
        if message is None:
            return ""
        return str(message.get("editorial_node") or message.get("beat_id") or "").strip()

    @staticmethod
    def _requested_profile(*, preferred_name: str, story_gender: str) -> dict[str, object]:
        name = str(preferred_name or "").strip()
        gender = str(story_gender or "").strip()
        if not identity_is_complete(name, gender):
            raise ValueError("Informe o nome ou apelido e como deseja ser tratado na história.")
        if gender not in {"Como homem", "Como mulher", "De forma neutra"}:
            raise ValueError("Tratamento inválido para esta história.")
        return {
            "preferred_name": name,
            "name": name,
            "user_name": name,
            "story_gender": gender,
            "completed": True,
            "stage": 3,
        }

    @staticmethod
    def _profile(
        messages: list[dict[str, object]],
        requested_profile: dict[str, object],
    ) -> dict[str, object]:
        recovered = recover_persistent_profile(messages)
        if isinstance(recovered, dict):
            return dict(recovered)
        return dict(requested_profile)

    def _finish_loaded_run(
        self,
        *,
        context: RuntimePersistenceContext,
        user_id: str,
        package_id: str,
        block_id: str,
        beat_id: str,
    ) -> RuntimePersistenceContext:
        """Finaliza a run já carregada com uma única leitura autoritativa normal.

        ``update_run`` continua fazendo o ``force_refresh`` que protege a versão
        otimista. Só fazemos uma leitura adicional quando existe conflito real de
        concorrência. Assim o fechamento não precisa chamar ``get_active_run`` antes
        de cada update.
        """

        run = context.run
        if run is None:
            raise RuntimeError("A run não existe mais para ser finalizada.")
        if run.user_id != user_id or run.package_id != package_id:
            raise RuntimeConflictError("A run carregada não pertence ao usuário/pacote atual.")

        for attempt in range(2):
            expected_version = run.state_version
            now = utc_now_iso()
            run.current_block_id = block_id or run.current_block_id
            run.current_beat_id = beat_id or run.current_beat_id
            run.status = "completed"
            run.ending_code = "normal_completion"
            run.ended_at = now
            run.updated_at = now
            try:
                updated = self.repository.runs.update_run(
                    run=run,
                    expected_version=expected_version,
                )
            except RuntimeConflictError:
                if attempt:
                    raise
                refreshed = self.repository.get_active_run(
                    user_id=user_id,
                    package_id=package_id,
                )
                if refreshed is None:
                    existing = self.repository.get_run(run_id=run.run_id)
                    if existing is not None and existing.status == "completed":
                        context.run = existing
                        clear_paid_access_cache(user_id=user_id, package_id=package_id)
                        return context
                    raise
                if refreshed.run_id != run.run_id:
                    raise RuntimeConflictError(
                        "Outra run ativa apareceu durante o fechamento da execução atual."
                    )
                run = refreshed
                continue

            context.run = updated
            clear_paid_access_cache(user_id=user_id, package_id=package_id)
            return context

        return context

    def _load(
        self,
        account: Any,
        package_id: str,
        *,
        requested_profile: dict[str, object],
    ):
        package = require_editorial_package(package_id)
        script = load_editorial_package(self.secrets, package)
        user = self._user(account)
        context, state, messages = open_persistent_runtime(
            self.repository,
            user=user,
            package_id=package_id,
            package_version=str(script.raw.get("script_version", package.manifest.version)),
            restart=False,
            instance_id=f"flet_{user.user_id}",
        )
        profile = self._profile(messages, requested_profile)
        script = personalize_editorial_script(script, profile)
        if not is_frame_script(script):
            raise ValueError("Esta história ainda não usa quadros V2 compatíveis com o Flet.")
        return package, script, user, context, state, messages, profile

    def _generate(self, *, package, script, user, context, state, messages, profile, target_id):
        if not self.api_key:
            raise RuntimeError("OpenRouter não está configurado no servidor.")
        movement = (
            first_frame_movement(script)[1]
            if not target_id
            else movement_from_script(script, target_id)
        )
        if not target_id:
            target_id = first_frame_movement(script)[0]
        character_name, character_id = self._character(package)
        user_name = str(profile.get("preferred_name") or user.display_name or "").strip()
        prompt = build_runtime_prompt(
            character_name=character_name,
            user_name=user_name,
            movement=movement,
        ) + build_immersive_context(profile)
        history = [
            {"role": "assistant", "content": str(item.get("content", ""))}
            for item in messages[-8:]
            if str(item.get("role", "")) == "assistant"
        ]
        last_contract_error: FrameOutputContractError | None = None
        content = ""
        for attempt in range(2):
            generated = generate_response(
                api_key=self.api_key,
                model=self.model,
                system_prompt=prompt,
                history=history,
                user_text=frame_generation_instruction(attempt),
                debug_logging=not bool(build_immersive_context(profile)),
            ).strip()
            try:
                content = enforce_frame_output_contract(movement, generated)
                break
            except FrameOutputContractError as exc:
                last_contract_error = exc
                log_editorial_exception(
                    "flet_frame_contract",
                    exc,
                    user_id=user.user_id,
                    package_id=package.manifest.package_id,
                    frame_id=target_id,
                    attempt=attempt + 1,
                )
        if not content:
            raise RuntimeError(
                "O modelo não respeitou a estrutura obrigatória do quadro: "
                f"{last_contract_error}"
            )
        updated_state = state.copy()
        updated_state.step_index += 1
        updated_state.consumed_orders.append(updated_state.step_index)
        # Um quadro terminal ainda precisa ser revelado. A run só fica concluída
        # quando a última entry desse quadro é confirmada pelo cliente.
        updated_state.finished = False
        metadata: dict[str, object] = {
            "character_id": character_id,
            "editorial_node": target_id,
            "editorial_block": movement.block_id,
            "novel_v2": True,
            "novel_movement": True,
            "novel_frame": True,
            "novel_terminal_frame": bool(movement.is_ending),
            "input_source": "flet_api",
        }
        memory = persistent_profile_payload(profile)
        if memory and recover_persistent_profile(messages) is None:
            metadata["immersive_profile"] = memory
        context = persist_assistant_message(
            self.repository,
            context=context,
            user=user,
            state=updated_state,
            assistant_text=content,
            assistant_metadata=metadata,
            secrets=self.secrets,
        )
        messages.append({"role": "assistant", "content": content, **metadata})
        return context, updated_state, messages

    @staticmethod
    def _previous_image_id(script: Any, current_id: str) -> str:
        beat_ids = tuple(str(item or "").strip() for item in script.beats)
        if current_id not in beat_ids:
            return ""
        last = ""
        for beat_id in beat_ids[: beat_ids.index(current_id)]:
            try:
                movement = movement_from_script(script, beat_id)
                frame = novel_frame_patch._frame_from_movement(movement)
            except (KeyError, TypeError, ValueError):
                continue
            if not isinstance(frame, dict):
                continue
            base, sequence = image_sequence_for_frame(frame, inherited_image_id=last)
            if base:
                last = base
            for image_id in sequence:
                if image_id:
                    last = image_id
        return last

    @staticmethod
    def _image_url(package_id: str, *, image_id: str = "", node_id: str = "") -> str:
        query = "package_id=" + quote(package_id)
        if image_id:
            query += "&image_id=" + quote(image_id)
        elif node_id:
            query += "&node_id=" + quote(node_id)
        return "/api/v1/runs/image?" + query

    def _view(self, package, script, context, state, messages) -> RunFrame:
        current = self._current(messages)
        if current is None:
            raise RuntimeError("A run ainda não possui um quadro persistido.")
        content = str(current.get("content", "") or "")
        current_frame_id = frame_id(content)
        entry_count = frame_entry_count(content)
        if not current_frame_id:
            raise RuntimeError("A interação persistida não contém um quadro V2 válido.")
        node_id = self._movement_id(current)
        movement = movement_from_script(script, node_id)
        frame = novel_frame_patch._frame_from_movement(movement)
        image = resolve_editorial_scene_image(package.root, node_id)
        if image is None:
            image = resolve_numbered_beat_image(package.root, node_id, tuple(script.beats))
        image_url = ""
        if image is not None:
            image_url = self._image_url(package.manifest.package_id, node_id=node_id)
        entry_image_urls: tuple[str, ...] = ()
        if isinstance(frame, dict):
            inherited = self._previous_image_id(script, node_id)
            base_image_id, image_ids = image_sequence_for_frame(
                frame,
                inherited_image_id=inherited,
            )
            if base_image_id and resolve_narrative_image_id(package.root, base_image_id):
                image_url = self._image_url(
                    package.manifest.package_id,
                    image_id=base_image_id,
                )
            entry_image_urls = tuple(
                self._image_url(package.manifest.package_id, image_id=image_id)
                if image_id and resolve_narrative_image_id(package.root, image_id)
                else image_url
                for image_id in image_ids
            )
        return RunFrame(
            run_id=context.run.run_id if context.run is not None else "",
            package_id=package.manifest.package_id,
            frame_id=current_frame_id,
            content=content,
            image_url=image_url,
            revealed_entries=min(
                entry_count,
                max(
                    1 if entry_count else 0,
                    int(current.get("flet_revealed_entries", 0) or 0),
                ),
            ),
            entry_count=entry_count,
            entry_image_urls=entry_image_urls,
            finished=bool(state.finished),
        )

    def open(
        self,
        *,
        account: Any,
        package_id: str,
        preferred_name: str,
        story_gender: str,
    ) -> RunFrame:
        requested_profile = self._requested_profile(
            preferred_name=preferred_name,
            story_gender=story_gender,
        )
        with self._lock(account.user_id, package_id):
            values = self._load(
                account,
                package_id,
                requested_profile=requested_profile,
            )
            package, script, user, context, state, messages, profile = values
            current = self._current(messages)
            if current is None:
                context, state, messages = self._generate(
                    package=package,
                    script=script,
                    user=user,
                    context=context,
                    state=state,
                    messages=messages,
                    profile=profile,
                    target_id="",
                )
            elif recover_persistent_profile(messages) is None:
                memory = persistent_profile_payload(profile)
                if context.run is None or not memory:
                    raise RuntimeError("Não foi possível salvar o perfil desta história.")
                self.repository.persist_run_profile(
                    run_id=context.run.run_id,
                    user_id=user.user_id,
                    package_id=package_id,
                    profile=memory,
                )
                current["immersive_profile"] = memory
            return self._view(package, script, context, state, messages)

    def profile(self, *, account: Any, package_id: str) -> RunProfile:
        """Consulta a identidade de uma run ativa sem abrir ou carregar o roteiro."""

        with self._lock(account.user_id, package_id):
            run = self.repository.get_active_run(
                user_id=account.user_id,
                package_id=package_id,
            )
            if run is None:
                return RunProfile(False, str(account.display_name or "").strip(), "")
            messages = self.repository.list_interactions(
                run_id=run.run_id,
                limit=500,
            )
            recovered = recover_persistent_profile(messages)
            if not isinstance(recovered, dict):
                return RunProfile(False, str(account.display_name or "").strip(), "")
            preferred_name = str(recovered.get("preferred_name", "") or "").strip()
            story_gender = str(recovered.get("story_gender", "") or "").strip()
            return RunProfile(
                identity_is_complete(preferred_name, story_gender),
                preferred_name,
                story_gender,
            )

    def advance(
        self,
        *,
        account: Any,
        package_id: str,
        expected_frame_id: str,
        revealed_entries: int,
        preferred_name: str,
        story_gender: str,
    ) -> RunFrame:
        requested_profile = self._requested_profile(
            preferred_name=preferred_name,
            story_gender=story_gender,
        )
        with self._lock(account.user_id, package_id):
            package, script, user, context, state, messages, profile = self._load(
                account,
                package_id,
                requested_profile=requested_profile,
            )
            current = self._current(messages)
            if current is None:
                raise RuntimeError("A run não possui quadro atual.")
            content = str(current.get("content", "") or "")
            current_frame_id = frame_id(content)
            if current_frame_id != expected_frame_id:
                # Um clique duplicado pode chegar depois de o primeiro já ter
                # persistido o quadro seguinte. Nesse caso, devolver o estado
                # atual é idempotente e evita avançar duas vezes.
                if _is_idempotent_duplicate_advance(
                    script,
                    expected_frame_id=expected_frame_id,
                    current_movement_id=self._movement_id(current),
                ):
                    return self._view(package, script, context, state, messages)
                raise RuntimeError("O quadro informado não é mais o quadro atual.")
            persisted_reveal = int(current.get("flet_revealed_entries", 0) or 0)
            if persisted_reveal <= 0 and frame_entry_count(content):
                persisted_reveal = 1
            if min(int(revealed_entries), persisted_reveal) < frame_entry_count(content):
                raise PermissionError("Revele todas as falas e pensamentos antes do próximo quadro.")
            movement_id = self._movement_id(current)
            target = next_movement_id(script, movement_id)
            if not target:
                movement = movement_from_script(script, movement_id)
                state.finished = True
                context = self._finish_loaded_run(
                    context=context,
                    user_id=account.user_id,
                    package_id=package_id,
                    block_id=movement.block_id,
                    beat_id=movement_id,
                )
                return self._view(package, script, context, state, messages)
            context, state, messages = self._generate(
                package=package,
                script=script,
                user=user,
                context=context,
                state=state,
                messages=messages,
                profile=profile,
                target_id=target,
            )
            return self._view(package, script, context, state, messages)

    def reveal(
        self,
        *,
        account: Any,
        package_id: str,
        expected_frame_id: str,
        preferred_name: str,
        story_gender: str,
    ) -> RunFrame:
        requested_profile = self._requested_profile(
            preferred_name=preferred_name,
            story_gender=story_gender,
        )
        with self._lock(account.user_id, package_id):
            package, script, _user, context, state, messages, _profile = self._load(
                account,
                package_id,
                requested_profile=requested_profile,
            )
            current = self._current(messages)
            if current is None:
                raise RuntimeError("A run não possui quadro atual.")
            content = str(current.get("content", "") or "")
            if frame_id(content) != expected_frame_id:
                raise RuntimeError("O quadro informado não é mais o quadro atual.")
            total = frame_entry_count(content)
            previous = int(current.get("flet_revealed_entries", 0) or 0)
            if previous <= 0 and total:
                previous = 1
            revealed = self.repository.persist_frame_reveal(
                run_id=context.run.run_id,
                user_id=account.user_id,
                package_id=package_id,
                frame_id=expected_frame_id,
                revealed_entries=min(total, previous + 1),
            )
            current["flet_revealed_entries"] = revealed

            movement_id = self._movement_id(current)
            movement = movement_from_script(script, movement_id)
            if movement.is_ending and (total == 0 or revealed >= total):
                state.finished = True
                context = self._finish_loaded_run(
                    context=context,
                    user_id=account.user_id,
                    package_id=package_id,
                    block_id=movement.block_id,
                    beat_id=movement_id,
                )
            return self._view(package, script, context, state, messages)

    def image(
        self,
        *,
        package_id: str,
        node_id: str = "",
        image_id: str = "",
    ) -> Path | None:
        package = require_editorial_package(package_id)
        image = resolve_narrative_image_id(package.root, image_id) if image_id else None
        if image is None and node_id:
            image = resolve_editorial_scene_image(package.root, node_id)
        if image is None:
            script = load_editorial_package(self.secrets, package)
            if node_id:
                image = resolve_numbered_beat_image(package.root, node_id, tuple(script.beats))
        return Path(image["path"]) if image is not None else None


__all__ = ["FletRunService", "RunFrame"]
