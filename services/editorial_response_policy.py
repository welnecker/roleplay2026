from __future__ import annotations

# Mantém o módulo legado carregado para consumidores antigos e para o contrato
# público existente. O player editorial, porém, não usa mais seus regex para
# apagar a resposta antes da avaliação semântica.
from services.editorial_runtime_impl import clean_model_response as _legacy_clean_model_response


_TECHNICAL_MARKERS = (
    "<END_RUN",
    "END_RUN",
    '"event"',
    "```json",
)


def clean_editorial_progression_response(response: str, fallback: str) -> str:
    """Preserva a resposta natural e remove apenas vazios ou vazamentos técnicos.

    Restrições editoriais pertencem ao avaliador semântico. Esta etapa não pode
    apagar uma fala inteira por correspondência de regex de estilo ou narração.
    """

    value = str(response or "").strip()
    safe_fallback = str(fallback or "").strip()
    if not value:
        return safe_fallback
    lowered = value.casefold()
    if any(marker.casefold() in lowered for marker in _TECHNICAL_MARKERS):
        return safe_fallback
    return value


__all__ = ["clean_editorial_progression_response"]
