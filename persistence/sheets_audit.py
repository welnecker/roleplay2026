from __future__ import annotations

import logging
import os
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from time import monotonic
from typing import Any, Callable
from uuid import uuid4


_LOGGER = logging.getLogger("roleplay2026.sheets_audit")
_REQUEST_ID: ContextVar[str] = ContextVar("sheets_audit_request_id", default="-")
_REQUEST_ROUTE: ContextVar[str] = ContextVar("sheets_audit_request_route", default="-")
_QUOTA_SEEN: ContextVar[bool] = ContextVar("sheets_audit_quota_seen", default=False)
_COUNTERS: dict[tuple[str, str], int] = {}
_COUNTERS_LOCK = Lock()
_INSTALL_LOCK = Lock()
_INSTALLED = False


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


def _increment(sheet: str, metric: str, amount: int) -> None:
    if not amount:
        return
    key = (sheet, metric)
    _COUNTERS[key] = _COUNTERS.get(key, 0) + amount


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
    logical_request: bool = False,
) -> None:
    if not enabled():
        return

    dimensions = {
        "requests": int(logical_request),
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
            _increment(sheet, metric, increment)
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


def _worksheet_title(worksheet: Any) -> str:
    title = str(getattr(worksheet, "title", "") or "").strip()
    return title or "UNKNOWN"


def _install_gspread_probes() -> None:
    """Instrumenta os métodos-folha usados pelo app para não contar duas vezes.

    ``get_all_records`` e ``row_values`` delegam para ``Worksheet.get``;
    ``append_row`` delega para ``append_rows``. Monitorar os dois níveis faria
    uma única chamada HTTP parecer duas leituras/escritas.
    """

    from gspread import Worksheet
    from gspread.exceptions import APIError

    from persistence.google_sheets_retry import is_quota_error

    operations = {
        "get": (1, 0),
        "batch_get": (1, 0),
        "append_rows": (0, 1),
        "update": (0, 1),
        "batch_update": (0, 1),
        "delete_rows": (0, 1),
        "insert_rows": (0, 1),
    }

    for method_name, (google_read, google_write) in operations.items():
        original = getattr(Worksheet, method_name, None)
        if original is None or getattr(original, "_sheets_audit_wrapped", False):
            continue

        def make_wrapper(
            method: Callable[..., Any],
            name: str,
            read_count: int,
            write_count: int,
        ) -> Callable[..., Any]:
            @wraps(method)
            def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
                started = monotonic()
                sheet = _worksheet_title(self)
                try:
                    result = method(self, *args, **kwargs)
                except APIError as exc:
                    quota = is_quota_error(exc)
                    if quota:
                        _QUOTA_SEEN.set(True)
                    emit(
                        sheet=sheet,
                        operation=f"google.{name}",
                        started_at=started,
                        google_read=read_count,
                        google_write=write_count,
                        status="429" if quota else "error",
                    )
                    raise
                emit(
                    sheet=sheet,
                    operation=f"google.{name}",
                    started_at=started,
                    google_read=read_count,
                    google_write=write_count,
                )
                return result

            setattr(wrapper, "_sheets_audit_wrapped", True)
            return wrapper

        setattr(
            Worksheet,
            method_name,
            make_wrapper(original, method_name, google_read, google_write),
        )


def _install_editorial_cache_probe() -> None:
    from persistence.editorial import GoogleSheetsEditorialRepository

    original = GoogleSheetsEditorialRepository._records
    if getattr(original, "_sheets_audit_wrapped", False):
        return

    @wraps(original)
    def records(self: Any, name: str) -> list[dict[str, Any]]:
        now = monotonic()
        cached = self._records_cache.get(name)
        cache = "HIT" if cached is not None and now < cached[0] else "MISS"
        quota_token = _QUOTA_SEEN.set(False)
        started = monotonic()
        try:
            result = original(self, name)
        except Exception:
            emit(
                sheet=name,
                operation="records",
                started_at=started,
                cache=cache,
                status="429" if _QUOTA_SEEN.get() else "error",
                logical_request=True,
            )
            raise
        else:
            stale = bool(_QUOTA_SEEN.get()) and cached is not None
            emit(
                sheet=name,
                operation="records",
                started_at=started,
                cache=cache,
                rows=len(result),
                stale_fallback=stale,
                logical_request=True,
            )
            return result
        finally:
            _QUOTA_SEEN.reset(quota_token)

    setattr(records, "_sheets_audit_wrapped", True)
    GoogleSheetsEditorialRepository._records = records


def _install_runtime_cache_probe() -> None:
    from persistence.v2_google_sheets import _SheetTable

    original = _SheetTable.records
    if getattr(original, "_sheets_audit_wrapped", False):
        return

    @wraps(original)
    def records(
        self: Any,
        *,
        force_refresh: bool = False,
        allow_stale_on_quota: bool = True,
    ) -> list[dict[str, Any]]:
        now = monotonic()
        cached = self._records_cache
        cache = (
            "HIT"
            if not force_refresh and cached is not None and now < cached[0]
            else "MISS"
        )
        quota_token = _QUOTA_SEEN.set(False)
        started = monotonic()
        try:
            result = original(
                self,
                force_refresh=force_refresh,
                allow_stale_on_quota=allow_stale_on_quota,
            )
        except Exception:
            emit(
                sheet=self.sheet_name,
                operation="records",
                started_at=started,
                cache=cache,
                status="429" if _QUOTA_SEEN.get() else "error",
                force_refresh=force_refresh,
                logical_request=True,
            )
            raise
        else:
            stale = bool(_QUOTA_SEEN.get()) and cached is not None
            emit(
                sheet=self.sheet_name,
                operation="records",
                started_at=started,
                cache=cache,
                rows=len(result),
                force_refresh=force_refresh,
                stale_fallback=stale,
                logical_request=True,
            )
            return result
        finally:
            _QUOTA_SEEN.reset(quota_token)

    setattr(records, "_sheets_audit_wrapped", True)
    _SheetTable.records = records


def install(app: Any) -> Any:
    """Ativa auditoria observacional sem alterar a semântica dos repositórios.

    Quando ``SHEETS_AUDIT_ENABLED`` não está ativo, esta função é um no-op.
    Os wrappers não registram conteúdo de células, credenciais, e-mails ou senhas.
    """

    global _INSTALLED
    if not enabled():
        return app

    with _INSTALL_LOCK:
        if not _INSTALLED:
            _install_gspread_probes()
            _install_editorial_cache_probe()
            _install_runtime_cache_probe()
            _INSTALLED = True

    if not getattr(app.state, "sheets_audit_middleware_installed", False):
        @app.middleware("http")
        async def sheets_audit_request_context(request: Any, call_next: Any) -> Any:
            tokens = begin_request(request.method, request.url.path)
            try:
                return await call_next(request)
            finally:
                end_request(tokens)

        app.state.sheets_audit_middleware_installed = True

    _LOGGER.warning(
        "[SHEETS_AUDIT] enabled=true mode=observational sensitive_payloads=false"
    )
    return app
