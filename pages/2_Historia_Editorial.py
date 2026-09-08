from __future__ import annotations

from services.editorial_player import run_editorial_player


# Build marker deliberado: força o Streamlit Cloud a reiniciar esta página
# já com o player exclusivo da novela contínua V2.
NOVEL_V2_BUILD = "2026-08-17T15:15Z"

run_editorial_player()
