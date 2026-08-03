from __future__ import annotations

"""API genérica de preparação e progressão de roteiros editoriais."""

from services.supermarket_script_v2 import (
    automatic_followups_after,
    classify_contextual_user_message,
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
    state_after_automatic_followup,
)


prepare_editorial_script = prepare_supermarket_script_v2
decide_editorial_progression_turn = decide_supermarket_script_v2_turn
classify_contextual_editorial_message = classify_contextual_user_message
editorial_followups_after = automatic_followups_after
state_after_editorial_followup = state_after_automatic_followup


__all__ = [
    "classify_contextual_editorial_message",
    "decide_editorial_progression_turn",
    "editorial_followups_after",
    "prepare_editorial_script",
    "state_after_editorial_followup",
]
