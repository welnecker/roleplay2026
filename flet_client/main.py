from __future__ import annotations

from pathlib import Path

import flet as ft

from flet_client.frame_state import parse_visual_frame
from flet_client.frame_view import NovelFrameView
from flet_client.screens import BACKGROUND, library_screen, login_screen
from platform_core.catalog import load_demo_catalog
from platform_core.models import StoryCard


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

    def show(control: ft.Control) -> None:
        page.controls.clear()
        page.add(control)
        page.update()

    def show_player(_card: StoryCard) -> None:
        frame = parse_visual_frame(DEMO_FRAME)
        image = DEMO_IMAGE.read_bytes() if DEMO_IMAGE.is_file() else None

        def completed() -> None:
            page.show_dialog(
                ft.SnackBar(
                    ft.Text("Quadro demonstrativo concluído."),
                )
            )

        view = NovelFrameView(page, frame, image=image, on_frame_complete=completed)
        view.root.content.controls.insert(
            0,
            ft.TextButton(
                "← Voltar para os cards",
                style=ft.ButtonStyle(color="#FFFFFF"),
                on_click=lambda _event: show_library(),
            ),
        )
        show(view.root)

    def show_library() -> None:
        show(
            library_screen(
                load_demo_catalog(),
                display_name="Visitante",
                on_logout=show_login,
                on_open_preview=show_player,
            )
        )

    def show_login() -> None:
        show(login_screen(on_preview_login=show_library))

    show_login()


if __name__ == "__main__":
    ft.run(main)
