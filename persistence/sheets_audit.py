from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4


_LOGGER = logging.getLogger("roleplay2026.sheets_audit")
_REQUEST_ID: ContextVar[str] = ContextVar("sheets_audit_request_id", default="-")
_REQUEST_ROUTE: ContextVar[str] = ContextVar("sheets_audit_request_route", default="-")
_COUNTERS: dict[tuple[str, str], int] = {}
_COUNTERS_LOCK = Lock()


def enabled() -> bool:
    value = str(os.getenv("SHEETS_AUDIT_ENABLED", "") or "").strip().casefold()
    return value in {"1", "true", "yes", "on"}


def begin_request(method: str, route: str) -> tuple[Any, Any]:
    request_id = uuid4().hex[:8]
    return (
        _REQUEST_ID.set(request_id),
        _REQUEST_ROUTE.set(f"{method.upper()} {route}"),
    )


def end_request(tokens: tuple[Any, Any]) -> None:
    request_id_token, route_token = tokens
    _REQUEST_ID.reset(request_id_token)
    _REQUEST_ROUTE.reset(route_token)


def timer() -> float:
    return monotonic()


def emit(
    *,
    sheet: str,
    operation: str,
    started_at: float | None = None,
    cache: str = "-",
    google_read: int = 0,
    google_write: int = 0,
    rows: int | None = None,
    status: str = "ok",
    force_refresh: bool = False,
    stale_fallback: bool = False,
) -> None:
    if not enabled():
        return

    dimensions = {
        "requests": 1,
        "google_reads": int(bool(google_read)),
        "google_writes": int(bool(google_write)),
        "cache_hits": int(cache == "HIT"),
        "cache_misses": int(cache == "MISS"),
        "quota_429": int(status == "429"),
        "stale_fallbacks": int(stale_fallback),
        "force_refresh": int(force_refresh),
    }
    with _COUNTERS_LOCK:
        for metric, increment in dimensions.items():
            if increment:
                key = (sheet, metric)
                _COUNTERS[key] = _COUNTERS.get(key, 0) + increment
        sheet_totals = {
            metric: _COUNTERS.get((sheet, metric), 0)
            for metric in dimensions
        }

    duration_ms = (
        max(0.0, (monotonic() - started_at) * 1000.0)
        if started_at is not None
        else 0.0
    )
    row_value = "-" if rows is None else str(rows)
    _LOGGER.warning(
        "[SHEETS_AUDIT] req=%s route=%s sheet=%s op=%s cache=%s "
        "google_read=%d google_write=%d rows=%s duration_ms=%.1f status=%s "
        "force_refresh=%s stale=%s totals=%s",
        _REQUEST_ID.get(),
        _REQUEST_ROUTE.get(),
        sheet,
        operation,
        cache,
        google_read,
        google_write,
        row_value,
        duration_ms,
        status,
        str(force_refresh).lower(),
        str(stale_fallback).lower(),
        sheet_totals,
    )
