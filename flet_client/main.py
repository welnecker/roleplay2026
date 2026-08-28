from __future__ import annotations

import os
from pathlib import Path

import flet as ft

from flet_client.api_client import FletApiClient, FletApiError
from flet_client.frame_state import parse_visual_frame
from flet_client.frame_view import NovelFrameView
from flet_client.screens import BACKGROUND, library_screen, login_screen
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
    api_url = os.getenv("ROLEPLAY_FLET_API_URL", "").strip().rstrip("/")
    api_client = FletApiClient(api_url) if api_url else None
    active_cards: list[StoryCard] = []
    active_display_name = ""

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
                on_click=lambda _event: show_library(active_cards, active_display_name),
            ),
        )
        show(view.root)

    def show_library(cards: list[StoryCard], display_name: str) -> None:
        nonlocal active_cards, active_display_name
        active_cards = list(cards)
        active_display_name = display_name
        def logout() -> None:
            if api_client is not None:
                try:
                    api_client.logout()
                except FletApiError:
                    pass
            show_login()

        show(
            library_screen(
                cards,
                display_name=display_name,
                on_logout=logout,
                on_open_preview=show_player,
            )
        )

    def show_login() -> None:
        def authenticate(email: str, password: str) -> str | None:
            if api_client is None:
                return "Defina ROLEPLAY_FLET_API_URL antes de entrar."
            try:
                user = api_client.login(email=email, password=password)
                cards = api_client.catalog()
            except FletApiError as exc:
                return str(exc)
            show_library(cards, user.display_name or user.email)
            return None

        show(login_screen(on_login=authenticate, api_url=api_url))

    show_login()


if __name__ == "__main__":
    ft.run(main)
