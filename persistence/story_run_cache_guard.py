from __future__ import annotations

"""Protege a descoberta de runs ativas contra cache vazio obsoleto.

STORY_RUNS pode ser escrita por outro repositório/fluxo do mesmo processo
(ex.: criação da run após crédito/pagamento). Um cache local vazio não pode
ser tratado como prova autoritativa de que a run continua inexistente.

A política é assimétrica de propósito:
- resultado positivo usa normalmente o cache longo de leitura;
- resultado vazio é confirmado uma única vez com ``force_refresh=True``.

Isso preserva a redução de leituras durante a história sem manter um falso
"nenhuma run" por dezenas de segundos.
"""

from typing import Any

from persistence import v2_google_sheets as v2_module


_INSTALLED = False


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
        run = original(self, user_id=user_id, package_id=package_id)
        if run is not None:
            return run

        # Um cache vazio pode ter sido preenchido antes de outra camada criar
        # a run. Confirme a ausência diretamente no Sheets antes de devolver
        # None. Se a run existir, a leitura autoritativa também renova o cache.
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
