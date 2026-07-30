from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import streamlit as st

from narrative_v2.models import StoryRun
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository, RuntimeSession
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState
from services.paid_run_access import finish_active_run
from services.v2_run_starter import start_v2_run_on_first_message


INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent.parent / "installed_stories"


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

    @property
    def save(self) -> RuntimeRunView:
        """Compatibilidade temporária para telas que ainda exibem o antigo save."""
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


def _state_from_messages(messages: list[dict[str, object]]) -> StoryState:
    for message in reversed(messages):
        raw = message.get("_story_state")
        if isinstance(raw, dict):
            return restore_story_state(raw)
    assistant_count = sum(1 for item in messages if str(item.get("role", "")) == "assistant")
    return StoryState(
        step_index=assistant_count,
        consumed_orders=list(range(1, assistant_count + 1)),
        finished=False,
    )


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
    if run is not None:
        session = repository.create_session(
            run_id=run.run_id,
            user_id=user.user_id,
            package_id=package_id,
            instance_id=resolved_instance,
        )
        messages = repository.list_interactions(run_id=run.run_id, limit=100)

    context = RuntimePersistenceContext(
        package_id=package_id,
        package_version=package_version,
        run=run,
        session=session,
        instance_id=resolved_instance,
    )
    return context, _state_from_messages(messages), messages


def persist_turn(
    repository: GoogleSheetsV2RuntimeRepository,
    *,
    context: RuntimePersistenceContext,
    user: AuthenticatedUser,
    state: StoryState,
    user_text: str,
    assistant_text: str,
    assistant_metadata: dict[str, object],
    sequence_start: int,
) -> RuntimePersistenceContext:
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

    block_id = str(
        assistant_metadata.get("screenplay_route")
        or assistant_metadata.get("pilot_node")
        or run.current_block_id
    )
    beat_id = str(
        assistant_metadata.get("screenplay_beat")
        or assistant_metadata.get("pilot_node")
        or run.current_beat_id
    )
    persisted_metadata = dict(assistant_metadata)
    persisted_metadata["_story_state"] = serialize_story_state(state)

    repository.append_interaction(
        run_id=run.run_id,
        session_id=session.session_id,
        user_id=user.user_id,
        package_id=context.package_id,
        role="user",
        speaker_id="user",
        content=user_text,
        sequence=sequence_start,
        block_id=block_id,
        beat_id=beat_id,
    )
    repository.append_interaction(
        run_id=run.run_id,
        session_id=session.session_id,
        user_id=user.user_id,
        package_id=context.package_id,
        role="assistant",
        speaker_id="mary",
        content=assistant_text,
        sequence=sequence_start + 1,
        block_id=block_id,
        beat_id=beat_id,
        metadata=persisted_metadata,
    )

    if state.finished:
        requested_status = str(
            assistant_metadata.get("pilot_run_status", "completed") or "completed"
        )
        run_status = "terminated" if requested_status == "terminated" else "completed"
        ending_code = str(
            assistant_metadata.get("pilot_ending_code", "normal_completion")
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
        run = repository.update_run_progress(
            run=run,
            block_id=block_id,
            beat_id=beat_id,
        )

    return RuntimePersistenceContext(
        package_id=context.package_id,
        package_version=context.package_version,
        run=run,
        session=session,
        instance_id=context.instance_id,
    )
