from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from gspread.exceptions import APIError


T = TypeVar("T")
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def api_error_status(exc: APIError) -> int | None:
    value = getattr(getattr(exc, "response", None), "status_code", None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def with_transient_retry(
    operation: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay_seconds: float = 1.0,
) -> T:
    """Repete indisponibilidades transitórias do Google sem mascarar erros permanentes."""

    if attempts < 1:
        raise ValueError("attempts deve ser maior ou igual a 1.")
    for attempt in range(attempts):
        try:
            return operation()
        except APIError as exc:
            if (
                api_error_status(exc) not in TRANSIENT_STATUS_CODES
                or attempt == attempts - 1
            ):
                raise
            time.sleep(base_delay_seconds * (2**attempt))
    raise RuntimeError("Retentativa do Google Sheets terminou inesperadamente.")


__all__ = ["TRANSIENT_STATUS_CODES", "api_error_status", "with_transient_retry"]
