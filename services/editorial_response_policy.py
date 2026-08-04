from __future__ import annotations

import re


_TECHNICAL_MARKERS = (
    "<END_RUN",
    "END_RUN",
    '"event"',
    "```json",
)

_LEGACY_FORBIDDEN_NARRATION = (
    r"\bMary\s+(?:sorri|ri|olha|observa|caminha|segura|recu[aá]|respira|inclina|aproxima|afasta|encosta|vira|cruza|levanta|abaixa)\b",
    r"\bela\s+",
    r"\b(?:eu\s+)?(?:arregalo|sorrio|rio|dou um passo|caminho|seguro|ajeito|observo|olho|recuo|respiro|inclino|aproximo|afasto|encosto|mantenho|viro|cruzo|descruzo|levanto|abaixo|mordo|lambo|chupo|beijo)\b",
    r"\b(?:meus?|minhas?)\s+(?:olhos|mãos|lábios|pernas|braços|dedos)\b",
    r"\b(?:contato visual|carrinho com as duas mãos|passo para trás|sorriso contido|risadinha curta)\b",
    r"\b(?:digo|pergunto|respondo|falo),?\s+(?:sorrindo|rindo|olhando|segurando|caminhando)\b",
)


def clean_editorial_progression_response(response: str, fallback: str) -> str:
    """Limpa a resposta sem apagar a candidata do player editorial.

    O player editorial chama esta função com fallback vazio e delega restrições de
    estilo ao avaliador semântico. Consumidores legados usam fallback visível e
    preservam o bloqueio determinístico histórico de narração corporal.
    """

    value = str(response or "").strip()
    safe_fallback = str(fallback or "").strip()
    if not value:
        return safe_fallback

    lowered = value.casefold()
    if any(marker.casefold() in lowered for marker in _TECHNICAL_MARKERS):
        return safe_fallback

    if safe_fallback and any(
        re.search(pattern, value, flags=re.IGNORECASE)
        for pattern in _LEGACY_FORBIDDEN_NARRATION
    ):
        return safe_fallback

    return value


__all__ = ["clean_editorial_progression_response"]
