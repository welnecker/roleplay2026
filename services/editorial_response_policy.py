from __future__ import annotations

from services.editorial_runtime_impl import clean_model_response


def clean_editorial_progression_response(response: str, fallback: str) -> str:
    """Aplica a limpeza padrão do runtime à resposta gerada para a progressão."""

    return clean_model_response(response, fallback)


__all__ = ["clean_editorial_progression_response"]
