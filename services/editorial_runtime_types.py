from __future__ import annotations

"""Contrato nominal dos tipos do runtime editorial.

A implementação histórica ainda define os objetos concretos em
``editorial_runtime_impl``. Este módulo concentra os nomes editoriais usados
pelo código de produção durante a etapa final de migração.
"""

from services.editorial_runtime_impl import (
    Engagement as EditorialEngagement,
    PilotScript as EditorialScript,
    PilotState as EditorialState,
    PilotTurn as EditorialTurn,
)


__all__ = [
    "EditorialEngagement",
    "EditorialScript",
    "EditorialState",
    "EditorialTurn",
]
