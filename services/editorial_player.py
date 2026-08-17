from __future__ import annotations

import importlib
import sys
from types import ModuleType


_RUNTIME_MODULE = "services.novel_player_runtime"


def _load_or_reload_runtime() -> ModuleType:
    """Executa exclusivamente o player da novela contínua nesta branch V2."""

    loaded = sys.modules.get(_RUNTIME_MODULE)
    if loaded is None:
        return importlib.import_module(_RUNTIME_MODULE)

    registered = sys.modules.get(_RUNTIME_MODULE)
    if registered is None:
        return importlib.import_module(_RUNTIME_MODULE)

    try:
        return importlib.reload(registered)
    except ImportError:
        current = sys.modules.get(_RUNTIME_MODULE)
        if current is None or current is not registered:
            return importlib.import_module(_RUNTIME_MODULE)
        raise


def run_editorial_player() -> None:
    """Executa o player V2: cena dramatizada -> Avançar -> próximo movimento."""

    _load_or_reload_runtime()


__all__ = ["run_editorial_player"]
