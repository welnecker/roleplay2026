from __future__ import annotations

import importlib


_RUNTIME_MODULE = "services.editorial_player_runtime"


def run_editorial_player() -> None:
    """Executa o player editorial selecionado pela plataforma.

    A implementação permanece em módulo separado durante a migração gradual do
    runtime histórico para as APIs públicas ``editorial_*``.
    """

    importlib.import_module(_RUNTIME_MODULE)


__all__ = ["run_editorial_player"]
