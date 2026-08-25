from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

from services.novel_frame_continuity_patch import install as install_novel_frame_continuity
from services.novel_frame_image_patch import install as install_novel_frame_image
from services.novel_frame_layout_patch import install as install_novel_frame_layout
from services.novel_frame_patch import install as install_novel_frame_v2
from services.novel_frame_presentation import install as install_novel_frame_presentation
from services.novel_frame_reveal_patch import install as install_novel_frame_reveal
from services.novel_frame_typography_patch import install as install_novel_frame_typography
from services.novel_run_version_guard import install as install_novel_run_version_guard
from services.novel_synced_image_carousel import install as install_synced_image_carousel
from services.novel_synced_image_carousel_autoscroll import install as install_synced_carousel_autoscroll
from services.novel_synced_image_carousel_desktop import install as install_synced_desktop_carousel
from services.novel_synced_visual_contract import install as install_synced_visual_contract


_RUNTIME_PATH = Path(__file__).with_name("novel_player_runtime.py")
NOVEL_FRAME_BUILD = "2026-08-25.synced-image-carousel.10"
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
    install_novel_run_version_guard()
    install_novel_frame_v2()
    install_novel_frame_continuity()
    install_novel_frame_reveal()
    install_novel_frame_presentation()
    install_novel_frame_typography()
    install_novel_frame_image()
    install_novel_frame_layout()
    install_synced_image_carousel()
    install_synced_desktop_carousel()
    install_synced_carousel_autoscroll()
    install_synced_visual_contract()
    if not _BUILD_LOGGED:
        print(
            f"[NOVEL_FRAME_BUILD] {NOVEL_FRAME_BUILD} — "
            "carrossel imagem+balão sincronizado com foco automático no slide mais recente, enquadramento integral sem crop, balões padronizados com caudas consistentes, tipografia editorial, binding de versão e continuidade canônica autoritativa"
        )
        _BUILD_LOGGED = True

    return runpy.run_path(str(_RUNTIME_PATH), run_name="services.novel_player_runtime.__streamlit__")


def run_editorial_player() -> None:
    """Executa o player V2 com compatibilidade para quadros legados."""

    _execute_runtime()


__all__ = ["NOVEL_FRAME_BUILD", "run_editorial_player"]
