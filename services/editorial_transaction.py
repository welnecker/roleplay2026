from __future__ import annotations

from dataclasses import dataclass

from services.editorial_beat_context import BeatContext, build_beat_context
from services.editorial_phase_contract import adapt_context_for_runtime_phase
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


@dataclass(frozen=True, slots=True)
class PendingEditorialTurn:
    previous_state: EditorialState
    proposed_state: EditorialState
    turn: EditorialTurn
    context: BeatContext
    prompt: str


@dataclass(frozen=True, slots=True)
class CommittedEditorialTurn:
    response: str
    state: EditorialState
    turn: EditorialTurn


def prepare_pending_editorial_turn(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> PendingEditorialTurn:
    context = adapt_context_for_runtime_phase(
        build_beat_context(script, previous_state, turn),
        turn.state,
    )
    return PendingEditorialTurn(
        previous_state=EditorialState.from_dict(previous_state.to_dict()),
        proposed_state=EditorialState.from_dict(turn.state.to_dict()),
        turn=turn,
        context=context,
        prompt=turn.system_prompt,
    )


def commit_editorial_turn(
    pending: PendingEditorialTurn,
    response: str,
) -> CommittedEditorialTurn:
    approved = str(response or "").strip()
    if not approved:
        raise ValueError("Uma resposta vazia não pode ser commitada.")
    return CommittedEditorialTurn(
        response=approved,
        state=EditorialState.from_dict(pending.proposed_state.to_dict()),
        turn=pending.turn,
    )


__all__ = [
    "CommittedEditorialTurn",
    "PendingEditorialTurn",
    "commit_editorial_turn",
    "prepare_pending_editorial_turn",
]
