from __future__ import annotations

"""API estável do runtime editorial.

A implementação histórica ainda vive em ``pilot_supermarket`` durante a migração.
Novos consumidores devem importar somente deste módulo.
"""

from services.pilot_supermarket import (
    Engagement,
    PilotScript,
    PilotState,
    PilotTurn,
    classify_user_message,
    clean_model_response,
    decide_turn,
    opening_text,
)


EditorialEngagement = Engagement
EditorialScript = PilotScript
EditorialState = PilotState
EditorialTurn = PilotTurn
classify_editorial_user_message = classify_user_message
decide_editorial_turn = decide_turn
clean_editorial_model_response = clean_model_response
editorial_opening_text = opening_text


__all__ = [
    "EditorialEngagement",
    "EditorialScript",
    "EditorialState",
    "EditorialTurn",
    "classify_editorial_user_message",
    "clean_editorial_model_response",
    "decide_editorial_turn",
    "editorial_opening_text",
]
