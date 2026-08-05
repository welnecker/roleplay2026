from __future__ import annotations

"""API pública do runtime editorial.

A decisão pública de turno passa pelo motor oficial ``beat -> ponte -> beat/pátio``.
Nenhuma função global é substituída durante a inicialização do player.
"""

from services.editorial_progression import clean_editorial_progression_response
from services.editorial_runtime_impl import classify_user_message, opening_text
from services.editorial_runtime_types import (
    EditorialEngagement,
    EditorialScript,
    EditorialState,
    EditorialTurn,
)
from services.editorial_turn_engine import decide_editorial_turn


classify_editorial_user_message = classify_user_message
clean_editorial_model_response = clean_editorial_progression_response
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
