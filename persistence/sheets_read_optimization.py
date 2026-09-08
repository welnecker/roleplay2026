from __future__ import annotations

"""Política de leitura para o runtime Flet sobre Google Sheets.

A persistência continua autoritativa no Sheets. Este módulo reduz releituras
repetidas dentro do mesmo processo, sem agrupar, atrasar ou eliminar writes de
INTERACTIONS. Operações de concorrência que usam ``force_refresh=True`` em
STORY_RUNS continuam ignorando o cache.
"""

import os
from time import monotonic
from typing import Any

from persistence import accounts as accounts_module
from persistence import editorial as editorial_module
from persistence import runtime_v2 as runtime_module
from persistence import v2_google_sheets as v2_module


_INSTALLED = False


def _env_seconds(name: str, default: float, *, minimum: float = 0.0) -> float:
    raw = str(os.environ.get(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def cache_ttl_for(sheet_name: str) -> float:
    """TTL por aba; INTERACTIONS preserva a janela curta existente."""

    name = str(sheet_name or "").strip().upper()
    defaults = {
        "STORY_RUNS": 60.0,
        "RUN_MEMORIES": 300.0,
        "SESSIONS": 600.0,
        "INTERACTIONS": 20.0,
        "STORY_CREDITS": 60.0,
    }
    default = defaults.get(name, 20.0)
    env_name = f"SHEETS_CACHE_TTL_{name}_SECONDS" if name else ""
    return _env_seconds(env_name, default, minimum=1.0) if env_name else default


def roteiros_cache_ttl() -> float:
    return _env_seconds("SHEETS_CACHE_TTL_ROTEIROS_SECONDS", 180.0, minimum=10.0)


def users_lookup_cache_ttl() -> float:
    return _env_seconds("SHEETS_CACHE_TTL_USERS_SECONDS", 120.0, minimum=10.0)


def _install_runtime_table_policy() -> None:
    base = v2_module._SheetTable
    if getattr(base, "_read_optimization_policy", False):
        return

    class PolicySheetTable(base):
        _read_optimization_policy = True

        @property
        def cache_ttl_seconds(self) -> float:
            return cache_ttl_for(self.sheet_name)

        def _extend_cache_window(self) -> None:
            cached = self._records_cache
            if cached is None:
                return
            self._records_cache = (
                monotonic() + self.cache_ttl_seconds,
                [dict(row) for row in cached[1]],
            )

        def records(
            self,
            *,
            force_refresh: bool = False,
            allow_stale_on_quota: bool = True,
        ) -> list[dict[str, Any]]:
            rows = super().records(
                force_refresh=force_refresh,
                allow_stale_on_quota=allow_stale_on_quota,
            )
            # ``force_refresh`` continua sendo uma leitura real e autoritativa;
            # após ela, o resultado recém-lido também pode alimentar a janela.
            self._extend_cache_window()
            return rows

        def append(self, data: dict[str, Any]) -> None:
            super().append(data)
            # O append já aconteceu no Google. Apenas prolongamos a cópia local
            # que o próprio repositório atualizou, inclusive em INTERACTIONS.
            self._extend_cache_window()

        def replace(self, row_number: int, data: dict[str, Any]) -> None:
            super().replace(row_number, data)
            self._extend_cache_window()

    # Os dois módulos mantêm uma referência própria ao nome _SheetTable.
    # Trocá-las antes da criação dos repositórios faz novas tabelas nascerem
    # com a política sem alterar os contratos públicos dos repositórios.
    v2_module._SheetTable = PolicySheetTable
    runtime_module._SheetTable = PolicySheetTable


def _install_session_identity_cache() -> None:
    cls = runtime_module.GoogleSheetsV2RuntimeRepository
    original = cls.create_session
    if getattr(original, "_read_optimization_policy", False):
        return

    def create_session(
        self: Any,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        instance_id: str,
    ) -> Any:
        key = (
            str(run_id or "").strip(),
            str(user_id or "").strip(),
            str(package_id or "").strip(),
            str(instance_id or "").strip(),
        )
        cache = getattr(self, "_active_runtime_sessions", None)
        if cache is None:
            cache = {}
            setattr(self, "_active_runtime_sessions", cache)
        existing = cache.get(key)
        if existing is not None and str(getattr(existing, "status", "")) == "active":
            return existing
        session = original(
            self,
            run_id=run_id,
            user_id=user_id,
            package_id=package_id,
            instance_id=instance_id,
        )
        if str(getattr(session, "status", "")) == "active":
            cache[key] = session
        return session

    setattr(create_session, "_read_optimization_policy", True)
    cls.create_session = create_session


def _install_user_lookup_cache() -> None:
    cls = accounts_module.GoogleSheetsAccountRepository
    original = cls.get_user
    if getattr(original, "_read_optimization_policy", False):
        return

    def get_user(self: Any, *, user_id: str) -> Any:
        clean = str(user_id or "").strip()
        now = monotonic()
        cache = getattr(self, "_user_lookup_cache", None)
        if cache is None:
            cache = {}
            setattr(self, "_user_lookup_cache", cache)
        cached = cache.get(clean)
        if cached is not None and now < cached[0]:
            return cached[1]
        user = original(self, user_id=clean)
        # Usuário ativo: janela maior. Ausência/inatividade fica curta para não
        # atrasar cadastro ou reativação durante testes administrativos.
        ttl = users_lookup_cache_ttl() if user is not None else 15.0
        cache[clean] = (now + ttl, user)
        return user

    setattr(get_user, "_read_optimization_policy", True)
    cls.get_user = get_user


def _install_roteiros_cache() -> None:
    cls = editorial_module.GoogleSheetsEditorialRepository
    original_records = cls._records
    original_append = cls._append
    if getattr(original_records, "_read_optimization_policy", False):
        return

    def records(self: Any, name: str) -> list[dict[str, Any]]:
        if str(name or "").strip().upper() != "ROTEIROS":
            return original_records(self, name)
        now = monotonic()
        cached = getattr(self, "_runtime_roteiros_cache", None)
        if cached is not None and now < cached[0]:
            return [dict(row) for row in cached[1]]
        rows = original_records(self, name)
        setattr(
            self,
            "_runtime_roteiros_cache",
            (now + roteiros_cache_ttl(), [dict(row) for row in rows]),
        )
        return [dict(row) for row in rows]

    def append(self: Any, name: str, data: dict[str, Any]) -> None:
        original_append(self, name, data)
        if str(name or "").strip().upper() == "ROTEIROS":
            setattr(self, "_runtime_roteiros_cache", None)

    setattr(records, "_read_optimization_policy", True)
    setattr(append, "_read_optimization_policy", True)
    cls._records = records
    cls._append = append


def install() -> None:
    """Instala a política antes de os repositórios do app serem construídos."""

    global _INSTALLED
    if _INSTALLED:
        return
    _install_runtime_table_policy()
    _install_session_identity_cache()
    _install_user_lookup_cache()
    _install_roteiros_cache()
    _INSTALLED = True


__all__ = [
    "cache_ttl_for",
    "install",
    "roteiros_cache_ttl",
    "users_lookup_cache_ttl",
]
