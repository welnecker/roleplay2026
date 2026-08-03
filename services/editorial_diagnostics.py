from __future__ import annotations

"""API pública de diagnóstico e proteção de respostas editoriais."""

import json
import logging
import sys

from services.editorial_diagnostics_impl import (
    GuardedResponse,
    build_turn_diagnostics,
    finalize_model_response,
    log_exception as _log_exception,
    log_turn,
)


LOGGER = logging.getLogger("editorial.pilot")
EditorialGuardedResponse = GuardedResponse
build_editorial_turn_diagnostics = build_turn_diagnostics
finalize_editorial_model_response = finalize_model_response
log_editorial_turn = log_turn


def log_editorial_exception(stage: str, exc: BaseException, **context: object) -> None:
    """Registra exceções reais com traceback e eventos sintéticos sem ``NoneType``.

    Alguns fluxos rejeitam uma resposta por decisão editorial, fora de um bloco
    ``except``. Nesses casos não existe traceback ativo; registrar com
    ``LOGGER.exception`` produz apenas ``NoneType: None`` e mascara o evento.
    """

    if sys.exc_info()[0] is not None:
        _log_exception(stage, exc, **context)
        return

    payload = {"stage": stage, **context}
    LOGGER.error(
        "pilot_error %s | %s",
        json.dumps(payload, ensure_ascii=False, default=str),
        exc,
    )


__all__ = [
    "EditorialGuardedResponse",
    "build_editorial_turn_diagnostics",
    "finalize_editorial_model_response",
    "log_editorial_exception",
    "log_editorial_turn",
]
