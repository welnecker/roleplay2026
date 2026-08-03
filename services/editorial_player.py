from __future__ import annotations

import importlib
import sys

from services.editorial_script_cache import refresh_loaded_editorial_script_cache


_RUNTIME_MODULE = "services.editorial_player_runtime"


def run_editorial_player() -> None:
    """Executa o player editorial em toda nova execução do Streamlit."""

    loaded = sys.modules.get(_RUNTIME_MODULE)
    if loaded is None:
        importlib.import_module(_RUNTIME_MODULE)
        return
    refresh_loaded_editorial_script_cache(loaded)
    importlib.reload(loaded)


__all__ = ["run_editorial_player"]
