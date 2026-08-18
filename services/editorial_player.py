from __future__ import annotations

import importlib
import sys
from types import ModuleType

from services.novel_frame_patch import install as install_novel_frame_v2
from services.novel_frame_presentation import install as install_novel_frame_presentation
from services.novel_frame_reveal_patch import install as install_novel_frame_reveal


_RUNTIME_MODULE = "services.novel_player_runtime"
NOVEL_FRAME_BUILD = "2026-08-18.1"
_BUILD_LOGGED = False


def _load_or_reload_runtime() -> ModuleType:
    """Executa exclusivamente o player da novela contínua nesta branch V2."""

    global _BUILD_LOGGED
    install_novel_frame_v2()
    install_novel_frame_reveal()
    install_novel_frame_presentation()
    if not _BUILD_LOGGED:
        print(f"[NOVEL_FRAME_BUILD] {NOVEL_FRAME_BUILD} — revelação incremental ativa")
        _BUILD_LOGGED = True

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
    """Executa o player V2: quadro dramatizado -> revelação -> próximo quadro."""

    _load_or_reload_runtime()


__all__ = ["NOVEL_FRAME_BUILD", "run_editorial_player"]
