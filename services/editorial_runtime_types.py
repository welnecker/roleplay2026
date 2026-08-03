from __future__ import annotations

"""Contrato nominal dos tipos do runtime editorial.

Todo o código de produção usa os nomes editoriais deste módulo. Os nomes
históricos permanecem encapsulados em ``editorial_runtime_impl`` somente para
preservar a suíte de regressão existente, sem contaminar os consumidores.
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
