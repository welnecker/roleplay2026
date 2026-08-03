from __future__ import annotations

"""API pública de diagnóstico e proteção de respostas editoriais."""

from services.editorial_diagnostics_impl import (
    GuardedResponse,
    build_turn_diagnostics,
    finalize_model_response,
    log_exception,
    log_turn,
)


EditorialGuardedResponse = GuardedResponse
build_editorial_turn_diagnostics = build_turn_diagnostics
finalize_editorial_model_response = finalize_model_response
log_editorial_exception = log_exception
log_editorial_turn = log_turn


__all__ = [
    "EditorialGuardedResponse",
    "build_editorial_turn_diagnostics",
    "finalize_editorial_model_response",
    "log_editorial_exception",
    "log_editorial_turn",
]
