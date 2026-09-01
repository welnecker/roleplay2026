from __future__ import annotations

"""Garante que uma conclusão normal nunca seja reaberta como continuação.

Uma run com ``status=completed`` representa uma compra já consumida. Se o usuário
quiser jogar novamente, precisa existir um novo crédito e uma nova ``run_id`` deve
ser criada desde o primeiro quadro.

Também repara de forma idempotente runs antigas que foram reativadas por versões
anteriores do runtime: se STORY_RUNS diz ``active`` mas o estado persistido em
INTERACTIONS já está ``finished=True``, fechamos essa run novamente antes de
prosseguir. O crédito novo, quando existir, permanece disponível para a nova run.
"""

from functools import wraps
from typing import Any

from flet_api.runs import FletRunService
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository
from services.paid_run_access import finish_active_run


_INSTALLED = False


def _is_normal_completion(run: Any) -> bool:
    return run is not None and str(getattr(run, "status", "") or "").strip() == "completed"


def _is_stale_active_terminal(context: Any, state: Any) -> bool:
    run = getattr(context, "run", None)
    return bool(
        run is not None
        and str(getattr(run, "status", "") or "").strip() == "active"
        and bool(getattr(state, "finished", False))
    )


def _invalidate_local_story_runs_cache(service: Any) -> None:
    repository = getattr(service, "repository", None)
    runs_repository = getattr(repository, "runs", None)
    table = getattr(runs_repository, "runs", None)
    if table is not None and hasattr(table, "_records_cache"):
        table._records_cache = None


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    repository_cls = GoogleSheetsV2RuntimeRepository
    original_resumable = repository_cls.get_resumable_completed_run
    if not getattr(original_resumable, "_completed_run_restart_guard", False):

        @wraps(original_resumable)
        def get_resumable_completed_run(
            self: Any,
            *,
            user_id: str,
            package_id: str,
        ) -> Any:
            candidate = original_resumable(
                self,
                user_id=user_id,
                package_id=package_id,
            )
            # Conclusão normal é terminal. Nunca reutilize a run/credit_id antigo.
            if _is_normal_completion(candidate):
                return None
            return candidate

        setattr(get_resumable_completed_run, "_completed_run_restart_guard", True)
        repository_cls.get_resumable_completed_run = get_resumable_completed_run

    service_cls = FletRunService
    original_load = service_cls._load
    if not getattr(original_load, "_completed_run_restart_guard", False):

        @wraps(original_load)
        def load_runtime(self: Any, account: Any, package_id: str):
            values = original_load(self, account, package_id)
            context = values[3]
            state = values[4]
            if not _is_stale_active_terminal(context, state):
                return values

            # Repara dados produzidos pelo comportamento antigo. Não revogamos
            # créditos disponíveis: um pagamento novo deve poder criar a nova run.
            finish_active_run(
                secrets=self.secrets,
                user_id=account.user_id,
                package_id=package_id,
                status="completed",
                ending_code="normal_completion",
            )
            # finish_active_run usa seu próprio repositório. Invalide a cópia local
            # para que a segunda carga veja imediatamente o status completed.
            _invalidate_local_story_runs_cache(self)
            return original_load(self, account, package_id)

        setattr(load_runtime, "_completed_run_restart_guard", True)
        service_cls._load = load_runtime

    _INSTALLED = True


__all__ = [
    "install",
    "_is_normal_completion",
    "_is_stale_active_terminal",
    "_invalidate_local_story_runs_cache",
]
