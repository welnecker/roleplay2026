from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

from services.novel_frame_image_patch import install as install_novel_frame_image
from services.novel_frame_layout_patch import install as install_novel_frame_layout
from services.novel_frame_patch import install as install_novel_frame_v2
from services.novel_frame_presentation import install as install_novel_frame_presentation
from services.novel_frame_reveal_patch import install as install_novel_frame_reveal


_RUNTIME_PATH = Path(__file__).with_name("novel_player_runtime.py")
NOVEL_FRAME_BUILD = "2026-08-18.11"
_BUILD_LOGGED = False


def _execute_runtime() -> dict[str, Any]:
    """Executa o player em namespace isolado para cada rerun do Streamlit.

    ``importlib.reload`` modifica a entrada global de ``sys.modules`` enquanto
    executa o arquivo. Dois reruns simultâneos podiam, portanto, remover ou
    substituir o módulo um do outro e repetir a abertura da mesma run. O player
    é um script Streamlit; executá-lo por caminho preserva esse contrato sem
    compartilhar estado de importação entre sessões.
    """

    global _BUILD_LOGGED
    install_novel_frame_v2()
    install_novel_frame_reveal()
    install_novel_frame_presentation()
    install_novel_frame_image()
    install_novel_frame_layout()
    if not _BUILD_LOGGED:
        print(
            f"[NOVEL_FRAME_BUILD] {NOVEL_FRAME_BUILD} — "
            "avanco inteligente por cards e composicao visual v2 ativos"
        )
        _BUILD_LOGGED = True

    return runpy.run_path(str(_RUNTIME_PATH), run_name="services.novel_player_runtime.__streamlit__")


def run_editorial_player() -> None:
    """Executa o player V2: CENA -> imagem -> cards incrementais horizontais."""

    _execute_runtime()


__all__ = ["NOVEL_FRAME_BUILD", "run_editorial_player"]
