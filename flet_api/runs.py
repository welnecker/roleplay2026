from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote

from packages.models import InstalledStoryPackage
from persistence.factory import build_google_sheets_repository
from platform_core.auth import AuthenticatedUser
from roleplay.openrouter import generate_response
from roleplay.models import StoryState
from services.editorial_content import load_editorial_package, require_editorial_package
from services.editorial_scene_images import (
    resolve_editorial_scene_image,
    resolve_numbered_beat_image,
)
from services.immersive_onboarding import (
    build_immersive_context,
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
from services.novel_v2_adapter import movement_from_script, next_movement_id
from services.runtime_persistence import (
    RuntimePersistenceContext,
    open_persistent_runtime,
    persist_assistant_message,
)
from services.paid_run_access import finish_active_run
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
    finished: bool = False


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
    def _profile(account: Any, messages: list[dict[str, object]]) -> dict[str, object]:
        recovered = recover_persistent_profile(messages)
        if isinstance(recovered, dict):
            return dict(recovered)
        return {
            "preferred_name": account.display_name,
            "name": account.display_name,
            "user_name": account.display_name,
        }

    def _load(self, account: Any, package_id: str):
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
        profile = self._profile(account, messages)
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
        if not content:
            raise RuntimeError(
                "O modelo não respeitou a estrutura obrigatória do quadro: "
                f"{last_contract_error}"
            )
        updated_state = state.copy()
        updated_state.step_index += 1
        updated_state.consumed_orders.append(updated_state.step_index)
        updated_state.finished = movement.is_ending
        metadata: dict[str, object] = {
            "character_id": character_id,
            "editorial_node": target_id,
            "editorial_block": movement.block_id,
            "novel_v2": True,
            "novel_movement": True,
            "novel_frame": True,
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
        if movement.is_ending:
            finish_active_run(
                secrets=self.secrets,
                user_id=user.user_id,
                package_id=package.manifest.package_id,
                status="completed",
                ending_code="normal_completion",
            )
        messages.append({"role": "assistant", "content": content, **metadata})
        return context, updated_state, messages

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
        image = resolve_editorial_scene_image(package.root, node_id)
        if image is None:
            image = resolve_numbered_beat_image(package.root, node_id, tuple(script.beats))
        image_url = ""
        if image is not None:
            image_url = "/api/v1/runs/image?package_id=" + quote(package.manifest.package_id) + "&node_id=" + quote(node_id)
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
            finished=bool(state.finished),
        )

    def open(self, *, account: Any, package_id: str) -> RunFrame:
        with self._lock(account.user_id, package_id):
            values = self._load(account, package_id)
            package, script, user, context, state, messages, profile = values
            if self._current(messages) is None:
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
            return self._view(package, script, context, state, messages)

    def advance(
        self,
        *,
        account: Any,
        package_id: str,
        expected_frame_id: str,
        revealed_entries: int,
    ) -> RunFrame:
        with self._lock(account.user_id, package_id):
            package, script, user, context, state, messages, profile = self._load(account, package_id)
            current = self._current(messages)
            if current is None:
                raise RuntimeError("A run não possui quadro atual.")
            content = str(current.get("content", "") or "")
            if frame_id(content) != expected_frame_id:
                raise RuntimeError("O quadro informado não é mais o quadro atual.")
            persisted_reveal = int(current.get("flet_revealed_entries", 0) or 0)
            if persisted_reveal <= 0 and frame_entry_count(content):
                persisted_reveal = 1
            if min(int(revealed_entries), persisted_reveal) < frame_entry_count(content):
                raise PermissionError("Revele todas as falas e pensamentos antes do próximo quadro.")
            target = next_movement_id(script, self._movement_id(current))
            if not target:
                state.finished = True
                finish_active_run(
                    secrets=self.secrets,
                    user_id=account.user_id,
                    package_id=package_id,
                    status="completed",
                    ending_code="normal_completion",
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
    ) -> RunFrame:
        with self._lock(account.user_id, package_id):
            package, script, _user, context, state, messages, _profile = self._load(
                account, package_id
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
            return self._view(package, script, context, state, messages)

    def image(self, *, package_id: str, node_id: str) -> Path | None:
        package = require_editorial_package(package_id)
        image = resolve_editorial_scene_image(package.root, node_id)
        if image is None:
            script = load_editorial_package(self.secrets, package)
            image = resolve_numbered_beat_image(package.root, node_id, tuple(script.beats))
        return Path(image["path"]) if image is not None else None


__all__ = ["FletRunService", "RunFrame"]
