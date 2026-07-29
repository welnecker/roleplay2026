from __future__ import annotations

import re
import unicodedata

from .models import Movement


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _tokens(value: str) -> set[str]:
    ignored = {"a", "as", "o", "os", "de", "do", "da", "e", "em", "um", "uma", "que"}
    return {
        token
        for token in re.findall(r"[a-z0-9]+", _normalize(value))
        if len(token) >= 3 and token not in ignored
    }


def enforce_movement(response: str, movement: Movement) -> tuple[str, bool]:
    """Retorna a resposta validada e informa se houve fallback determinístico."""
    expected = _tokens(movement.content)
    actual = _tokens(response)
    required = 1 if len(expected) <= 3 else 2
    if response.strip() and len(expected & actual) >= required:
        return response.strip(), False
    return movement.content.strip(), True
