from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from persistence.google_sheets import GoogleSheetsRuntimeRepository
from persistence.models import SaveRecord, SessionRecord
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState


@dataclass(slots=True)
class RuntimePersistenceContext:
    save: SaveRecord
    session: SessionRecord


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


def open_persistent_runtime(
    repository: GoogleSheetsRuntimeRepository,
    *,
    user: AuthenticatedUser,
    package_id: str,
    package_version: str,
    restart: bool = False,
    instance_id: str | None = None,
) -> tuple[RuntimePersistenceContext, StoryState, list[dict[str, object]]]:
    repository.upsert_user(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
    )

    save = None if restart else repository.get_active_save(
        user_id=user.user_id,
        package_id=package_id,
    )
    if save is None:
        save = repository.create_save(
            user_id=user.user_id,
            package_id=package_id,
            package_version=package_version,
            state=serialize_story_state(StoryState()),
        )

    session = repository.create_session(
        save_id=save.save_id,
        user_id=user.user_id,
        package_id=package_id,
        instance_id=instance_id or f"streamlit_{uuid4().hex}",
    )
    interactions = repository.list_interactions(save_id=save.save_id, limit=100)
    messages = [
        {
            "role": item.role,
            "content": item.content,
            **dict(item.metadata),
        }
        for item in interactions
    ]
    return (
        RuntimePersistenceContext(save=save, session=session),
        restore_story_state(save.state),
        messages,
    )


def persist_turn(
    repository: GoogleSheetsRuntimeRepository,
    *,
    context: RuntimePersistenceContext,
    user: AuthenticatedUser,
    state: StoryState,
    user_text: str,
    assistant_text: str,
    assistant_metadata: dict[str, object],
    sequence_start: int,
) -> RuntimePersistenceContext:
    repository.append_interaction(
        session_id=context.session.session_id,
        save_id=context.save.save_id,
        user_id=user.user_id,
        package_id=context.save.package_id,
        role="user",
        content=user_text,
        sequence=sequence_start,
    )
    repository.append_interaction(
        session_id=context.session.session_id,
        save_id=context.save.save_id,
        user_id=user.user_id,
        package_id=context.save.package_id,
        role="assistant",
        content=assistant_text,
        sequence=sequence_start + 1,
        metadata=assistant_metadata,
    )
    updated_save = repository.update_save(
        save_id=context.save.save_id,
        expected_version=context.save.state_version,
        state=serialize_story_state(state),
        status="completed" if state.finished else "active",
    )
    return RuntimePersistenceContext(save=updated_save, session=context.session)
