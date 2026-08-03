from __future__ import annotations

"""API pública do runtime editorial.

Os tipos e operações primitivas vivem em ``editorial_runtime_impl``. A decisão
pública de turno passa sempre pela progressão editorial completa, sem depender
de monkeypatch ou da ordem de importação dos módulos.
"""

from services.editorial_progression import (
    clean_editorial_progression_response,
    decide_editorial_progression_turn,
)
from services.editorial_runtime_impl import (
    classify_user_message,
    opening_text,
)
from services.editorial_runtime_types import (
    EditorialEngagement,
    EditorialScript,
    EditorialState,
    EditorialTurn,
)


classify_editorial_user_message = classify_user_message
decide_editorial_turn = decide_editorial_progression_turn
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
