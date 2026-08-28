from __future__ import annotations

from pathlib import Path

import flet as ft

from flet_client.frame_state import parse_visual_frame
from flet_client.frame_view import BACKGROUND, NovelFrameView


ROOT = Path(__file__).resolve().parent.parent
DEMO_IMAGE = ROOT / "installed_stories" / "casada_frustrada" / "assets" / "scenes" / "mary1.webp"
DEMO_FRAME = """[QUADRO encontro_demo]
[DESCRIÇÃO]
Mary entra na sala e observa o ambiente antes de continuar.
[PENSAMENTO mary|Mary]
Preciso entender o que está acontecendo antes de tomar qualquer decisão.
[FALA mary|Mary]
Olá... tem alguém aqui?
[FALA professor|Professor]
Pode entrar, Mary. Eu estava esperando por você.
[/QUADRO]"""


def main(page: ft.Page) -> None:
    page.title = "Entre Cenas — Player Flet"
    page.bgcolor = BACKGROUND
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT

    frame = parse_visual_frame(DEMO_FRAME)
    image = DEMO_IMAGE.read_bytes() if DEMO_IMAGE.is_file() else None

    def completed() -> None:
        page.show_dialog(
            ft.SnackBar(
                ft.Text("Quadro completo. A próxima fase conectará o frontend à API narrativa."),
            )
        )

    view = NovelFrameView(page, frame, image=image, on_frame_complete=completed)
    page.add(view.root)


if __name__ == "__main__":
    ft.run(main)

