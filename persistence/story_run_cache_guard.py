from __future__ import annotations

"""Protege a descoberta de runs ativas contra cache vazio obsoleto.

STORY_RUNS pode ser escrita por outro repositório/fluxo do mesmo processo
(ex.: criação da run após crédito/pagamento). Um cache local vazio não pode
ser tratado como prova autoritativa de que a run continua inexistente.

A política é assimétrica de propósito:
- resultado positivo usa normalmente o cache longo de leitura;
- uma leitura fresca que voltou vazia já é autoritativa e não é repetida;
- somente um resultado vazio servido por cache ainda válido é confirmado com
  ``force_refresh=True`` antes de ser tratado como ausência real.

Isso preserva a redução de leituras durante a história e a confirmação final
contra concorrência, sem duplicar uma leitura Google que acabou de acontecer.
"""

from time import monotonic
from typing import Any

from persistence import v2_google_sheets as v2_module


_INSTALLED = False


def _has_fresh_records_cache(table: Any) -> bool:
    cached = getattr(table, "_records_cache", None)
    if cached is None:
        return False
    try:
        expires_at = float(cached[0])
    except (IndexError, TypeError, ValueError):
        return False
    return monotonic() < expires_at


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    cls = v2_module.GoogleSheetsStoryRunRepository
    original = cls.get_active_run
    if getattr(original, "_story_run_empty_cache_guard", False):
        _INSTALLED = True
        return

    def get_active_run(
        self: Any,
        *,
        user_id: str,
        package_id: str,
    ) -> Any:
        # Capture o estado ANTES da consulta. Se não havia cache fresco, o
        # método original precisará consultar o Sheets; um None dessa leitura
        # recém-feita já é uma confirmação autoritativa e não deve provocar
        # uma segunda chamada idêntica.
        served_from_fresh_cache = _has_fresh_records_cache(self.runs)
        run = original(self, user_id=user_id, package_id=package_id)
        if run is not None or not served_from_fresh_cache:
            return run

        # Aqui o None veio de um cache vazio ainda válido. Esse é exatamente o
        # caso perigoso: outra instância/repositório pode ter criado a run após
        # o preenchimento do cache. Confirme diretamente no Sheets antes de
        # devolver ausência. Se a run existir, a leitura também renova o cache.
        rows = self.runs.records(
            force_refresh=True,
            allow_stale_on_quota=False,
        )
        candidates = [
            self._from_row(row)
            for row in rows
            if str(row.get("user_id", "")).strip() == str(user_id).strip()
            and str(row.get("package_id", "")).strip() == str(package_id).strip()
            and str(row.get("status", "")).strip() == "active"
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.updated_at, reverse=True)
        return candidates[0]

    setattr(get_active_run, "_story_run_empty_cache_guard", True)
    cls.get_active_run = get_active_run
    _INSTALLED = True


__all__ = ["install"]
