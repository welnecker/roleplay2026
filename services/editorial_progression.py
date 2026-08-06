from __future__ import annotations

"""API pública de preparação e progressão de roteiros editoriais."""

from services.editorial_followups import (
    editorial_followups_after,
    state_after_editorial_followup,
)
from services.editorial_message_policy import classify_contextual_editorial_message
from services.editorial_progression_gates import apply_progression_gate
from services.editorial_progression_impl import (
    decide_editorial_progression_turn as _decide_editorial_progression_turn,
    prepare_editorial_script,
)
from services.editorial_response_policy import clean_editorial_progression_response
from services.editorial_runtime_impl import decide_turn as base_decide_turn
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_turn_finalization import finalize_editorial_turn


def decide_editorial_progression_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn:
    """Decide o turno e aplica condições psicológicas reais de progressão."""

    turn = _decide_editorial_progression_turn(script, state, user_text)
    gated = apply_progression_gate(
        script,
        state,
        turn,
        user_text,
        base_decide=base_decide_turn,
    )
    if gated is turn:
        return turn
    return finalize_editorial_turn(script, gated)


__all__ = [
    "classify_contextual_editorial_message",
    "clean_editorial_progression_response",
    "decide_editorial_progression_turn",
    "editorial_followups_after",
    "prepare_editorial_script",
    "state_after_editorial_followup",
]
