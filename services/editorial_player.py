from __future__ import annotations

import importlib
import sys


_RUNTIME_MODULE = "services.editorial_player_runtime"


def run_editorial_player() -> None:
    """Executa o player editorial em toda nova execução do Streamlit."""

    loaded = sys.modules.get(_RUNTIME_MODULE)
    if loaded is None:
        importlib.import_module(_RUNTIME_MODULE)
        return
    importlib.reload(loaded)


__all__ = ["run_editorial_player"]
