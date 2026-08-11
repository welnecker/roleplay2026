from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import streamlit as st
import yaml

from narrative_v2.models import StoryRun
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository, RuntimeSession
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState
from services.paid_run_access import clear_paid_access_cache, finish_active_run
from services.v2_run_starter import start_v2_run_on_first_message


INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent.parent / "installed_stories"
RECOVERY_HISTORY_LIMIT = 500


@dataclass(frozen=True, slots=True)
class RuntimeRunView:
    save_id: str
    package_id: str
    state_version: int


@dataclass(slots=True)
class RuntimePersistenceContext:
    package_id: str
    package_version: str
    run: StoryRun | None = None
    session: RuntimeSession | None = None
    instance_id: str = ""
    next_sequence: int = 1

    @property
    def save(self) -> RuntimeRunView:
        return RuntimeRunView(
            save_id=self.run.run_id if self.run is not None else "aguardando_primeira_mensagem",
            package_id=self.package_id,
            state_version=self.run.state_version if self.run is not None else 0,
        )


def serialize_story_state(state: StoryState) -> dict[str, object]:
    return {
        "step_index": state.step_index,
        "consumed_orders": list(state.consumed_orders),
        "finished": state.finished,
    }


def restore_story_state(raw: dict[str, object]) -> StoryState:
    consumed = raw.get("consumed_orders", [])
    return StoryState(
        step_index=int(raw.get("step_index", 0) or 0),
        consumed_orders=[int(item) for item in consumed] if isinstance(consumed, list) else [],
        finished=bool(raw.get("finished", False)),
    )


def _ordered_messages(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        messages,
        key=lambda item: int(item.get("sequence", 0) or 0),
    )


def _state_from_messages(messages: list[dict[str, object]]) -> StoryState:
    for message in reversed(_ordered_messages(messages)):
        raw = message.get("_story_state")
        if isinstance(raw, dict):
            return restore_story_state(raw)

    assistant_messages = [
        item
        for item in _ordered_messages(messages)
        if str(item.get("role", "")) == "assistant"
    ]
    assistant_count = len(assistant_messages)
    return StoryState(
        step_index=assistant_count,
        consumed_orders=list(range(1, assistant_count + 1)),
        finished=False,
    )


def _next_sequence_from_messages(messages: list[dict[str, object]]) -> int:
    sequences = [
        int(item.get("sequence", 0) or 0)
        for item in messages
        if int(item.get("sequence", 0) or 0) > 0
    ]
    return max(sequences, default=0) + 1


def _current_story_max_order(package_id: str) -> int:
    """Lê somente a quantidade editorial necessária para decidir uma migração."""

    for package_root in INSTALLED_STORIES_ROOT.iterdir():
        manifest_path = package_root / "manifest.yaml"
        if not manifest_path.is_file():
            continue
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or str(manifest.get("package_id", "")) != package_id:
            continue
        entrypoint = str(manifest.get("entrypoint", "story.yaml") or "story.yaml")
        story_path = package_root / entrypoint
        story = yaml.safe_load(story_path.read_text(encoding="utf-8"))
        if not isinstance(story, dict):
            return 0
        orders: list[int] = []
        for route in story.get("routes", []) or []:
            if not isinstance(route, dict):
                continue
            for beat in route.get("beats", []) or []:
                if not isinstance(beat, dict):
                    continue
                for movement in beat.get("movements", []) or []:
                    if isinstance(movement, dict):
                        try:
                            orders.append(int(movement.get("order", 0) or 0))
                        except (TypeError, ValueError):
                            continue
        return max(orders, default=0)
    return 0


def _try_resume_completed_run(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    user: AuthenticatedUser,
    package_id: str,
) -> tuple[StoryRun | None, StoryState, list[dict[str, object]]]:
    candidate = repository.get_resumable_completed_run(
        user_id=user.user_id,
        package_id=package_id,
    )
    if candidate is None:
        return None, StoryState(), []

    messages = repository.list_interactions(
        run_id=candidate.run_id,
        limit=RECOVERY_HISTORY_LIMIT,
    )
    if not messages:
        return None, StoryState(), []

    state = _state_from_messages(messages)
    last_consumed_order = max(state.consumed_orders, default=0)
    if _current_story_max_order(package_id) <= last_consumed_order:
        return None, StoryState(), []

    run = repository.reactivate_run(candidate)
    state.finished = False
    clear_paid_access_cache(user_id=user.user_id, package_id=package_id)
    return run, state, _ordered_messages(messages)


def open_persistent_runtime(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    user: AuthenticatedUser,
    package_id: str,
    package_version: str,
    restart: bool = False,
    instance_id: str | None = None,
) -> tuple[RuntimePersistenceContext, StoryState, list[dict[str, object]]]:
    resolved_instance = instance_id or f"streamlit_{uuid4().hex}"
    run = None if restart else repository.get_active_run(
        user_id=user.user_id,
        package_id=package_id,
    )
    session: RuntimeSession | None = None
    messages: list[dict[str, object]] = []
    state = StoryState()

    if run is not None:
        messages = repository.list_interactions(
            run_id=run.run_id,
            limit=RECOVERY_HISTORY_LIMIT,
        )
        state = _state_from_messages(messages)
    elif not restart:
        run, state, messages = _try_resume_completed_run(
            repository,
            user=user,
            package_id=package_id,
        )

    if run is not None:
        session = repository.create_session(
            run_id=run.run_id,
            user_id=user.user_id,
            package_id=package_id,
            instance_id=resolved_instance,
        )

    context = RuntimePersistenceContext(
        package_id=package_id,
        package_version=package_version,
        run=run,
        session=session,
        instance_id=resolved_instance,
        next_sequence=_next_sequence_from_messages(messages),
    )
    return context, state, _ordered_messages(messages)


def _ensure_run_and_session(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    context: RuntimePersistenceContext,
    user: AuthenticatedUser,
) -> tuple[StoryRun, RuntimeSession]:
    run = context.run
    if run is None:
        run = start_v2_run_on_first_message(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=context.package_id,
            installed_stories_root=INSTALLED_STORIES_ROOT,
        )
        if run is None:
            raise RuntimeError(
                "Nenhum crédito disponível para iniciar esta execução. "
                "É necessário realizar um novo pagamento."
            )

    session = context.session
    if session is None or session.run_id != run.run_id:
        session = repository.create_session(
            run_id=run.run_id,
            user_id=user.user_id,
            package_id=context.package_id,
            instance_id=context.instance_id or f"streamlit_{uuid4().hex}",
        )
    return run, session


def _editorial_location(
    metadata: dict[str, object],
    run: StoryRun,
) -> tuple[str, str]:
    """Resolve o local efetivamente executado, sem reutilizar o início da run."""

    beat_id = str(
        metadata.get("editorial_node")
        or metadata.get("screenplay_beat")
        or metadata.get("pilot_node")
        or run.current_beat_id
    ).strip()
    block_id = str(
        metadata.get("editorial_block")
        or metadata.get("screenplay_route")
        or run.current_block_id
    ).strip()
    return block_id, beat_id


def persist_turn(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    context: RuntimePersistenceContext,
    user: AuthenticatedUser,
    state: StoryState,
    user_text: str,
    assistant_text: str,
    assistant_metadata: dict[str, object],
    sequence_start: int | None = None,
) -> RuntimePersistenceContext:
    del sequence_start
    run, session = _ensure_run_and_session(repository, context=context, user=user)

    block_id, beat_id = _editorial_location(assistant_metadata, run)
    persisted_metadata = dict(assistant_metadata)
    persisted_metadata["_story_state"] = serialize_story_state(state)
    character_id = str(persisted_metadata.get("character_id", "") or "character")

    persisted_sequence = max(1, int(context.next_sequence or 1))
    repository.append_interaction(
        run_id=run.run_id,
        session_id=session.session_id,
        user_id=user.user_id,
        package_id=context.package_id,
        role="user",
        speaker_id="user",
        content=user_text,
        sequence=persisted_sequence,
        block_id=block_id,
        beat_id=beat_id,
    )
    repository.append_interaction(
        run_id=run.run_id,
        session_id=session.session_id,
        user_id=user.user_id,
        package_id=context.package_id,
        role="assistant",
        speaker_id=character_id,
        content=assistant_text,
        sequence=persisted_sequence + 1,
        block_id=block_id,
        beat_id=beat_id,
        metadata=persisted_metadata,
    )

    if state.finished:
        requested_status = str(
            assistant_metadata.get("editorial_run_status")
            or assistant_metadata.get("pilot_run_status")
            or "completed"
        )
        run_status = "terminated" if requested_status == "terminated" else "completed"
        ending_code = str(
            assistant_metadata.get("editorial_ending_code")
            or assistant_metadata.get("pilot_ending_code")
            or "normal_completion"
        )
        finish_active_run(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=context.package_id,
            status=run_status,
            ending_code=ending_code,
        )
    else:
        run = repository.update_run_progress(run=run, block_id=block_id, beat_id=beat_id)

    return RuntimePersistenceContext(
        package_id=context.package_id,
        package_version=context.package_version,
        run=run,
        session=session,
        instance_id=context.instance_id,
        next_sequence=persisted_sequence + 2,
    )


def persist_opening_message(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    context: RuntimePersistenceContext,
    user: AuthenticatedUser,
    state: StoryState,
    assistant_text: str,
    assistant_metadata: dict[str, object],
) -> RuntimePersistenceContext:
    """Persiste a abertura exibida, uma única vez por run.

    A idempotência final pertence ao repositório: uma repetição causada por
    rerun do Streamlit encontra a mesma sequência, papel e conteúdo e não cria
    outra linha.
    """

    run, session = _ensure_run_and_session(repository, context=context, user=user)
    block_id, node_id = _editorial_location(assistant_metadata, run)
    persisted_metadata = dict(assistant_metadata)
    persisted_metadata["_story_state"] = serialize_story_state(state)
    persisted_metadata["opening_message"] = True
    character_id = str(persisted_metadata.get("character_id", "") or "character")
    sequence = max(1, int(context.next_sequence or 1))

    repository.append_interaction(
        run_id=run.run_id,
        session_id=session.session_id,
        user_id=user.user_id,
        package_id=context.package_id,
        role="assistant",
        speaker_id=character_id,
        content=assistant_text,
        sequence=sequence,
        block_id=block_id,
        beat_id=node_id,
        metadata=persisted_metadata,
    )
    run = repository.update_run_progress(
        run=run,
        block_id=block_id,
        beat_id=node_id,
    )
    return RuntimePersistenceContext(
        package_id=context.package_id,
        package_version=context.package_version,
        run=run,
        session=session,
        instance_id=context.instance_id,
        next_sequence=sequence + 1,
    )


def persist_assistant_message(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    context: RuntimePersistenceContext,
    user: AuthenticatedUser,
    state: StoryState,
    assistant_text: str,
    assistant_metadata: dict[str, object],
) -> RuntimePersistenceContext:
    """Registra uma ponte automática de Mary sem inventar uma fala do usuário."""

    run, session = _ensure_run_and_session(repository, context=context, user=user)
    block_id, beat_id = _editorial_location(assistant_metadata, run)
    persisted_metadata = dict(assistant_metadata)
    persisted_metadata["_story_state"] = serialize_story_state(state)
    persisted_metadata["automatic_bridge"] = True
    character_id = str(persisted_metadata.get("character_id", "") or "character")

    sequence = max(1, int(context.next_sequence or 1))
    repository.append_interaction(
        run_id=run.run_id,
        session_id=session.session_id,
        user_id=user.user_id,
        package_id=context.package_id,
        role="assistant",
        speaker_id=character_id,
        content=assistant_text,
        sequence=sequence,
        block_id=block_id,
        beat_id=beat_id,
        metadata=persisted_metadata,
    )
    run = repository.update_run_progress(run=run, block_id=block_id, beat_id=beat_id)
    return RuntimePersistenceContext(
        package_id=context.package_id,
        package_version=context.package_version,
        run=run,
        session=session,
        instance_id=context.instance_id,
        next_sequence=sequence + 1,
    )
