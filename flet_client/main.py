from __future__ import annotations

import os
import flet as ft

from flet_client.api_client import ApiPayment, ApiRunFrame, FletApiClient, FletApiError
from flet_client.frame_state import parse_visual_frame
from flet_client.frame_view import FrameVisualRow, NovelFrameView
from flet_client.screens import BACKGROUND, library_screen, login_screen, payment_screen
from platform_core.models import AccessStatus
from platform_core.models import StoryCard

DEFAULT_FLET_API_URL = "https://roleplay2026-flet-api.onrender.com"


def configured_api_url() -> str:
    return os.getenv("ROLEPLAY_FLET_API_URL", DEFAULT_FLET_API_URL).strip().rstrip("/")


def main(page: ft.Page) -> None:
    page.title = "Entre Cenas — Player Flet"
    page.bgcolor = BACKGROUND
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    api_url = configured_api_url()
    api_client = FletApiClient(api_url) if api_url else None
    active_cards: list[StoryCard] = []
    active_display_name = ""

    def show(control: ft.Control) -> None:
        page.controls.clear()
        page.add(control)
        page.update()

    def show_story_complete(card: StoryCard) -> None:
        show(
            ft.Container(
                expand=True,
                bgcolor=BACKGROUND,
                alignment=ft.Alignment.CENTER,
                padding=32,
                content=ft.Column(
                    tight=True,
                    spacing=18,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            "História concluída",
                            size=30,
                            weight=ft.FontWeight.BOLD,
                            color="#FFFFFF",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            card.title,
                            size=18,
                            color="#D6E5E3",
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.FilledButton(
                            "Voltar para os cards",
                            on_click=lambda _event: show_library(
                                active_cards,
                                active_display_name,
                            ),
                        ),
                    ],
                ),
            )
        )

    def show_player(
        card: StoryCard,
        current: ApiRunFrame | None = None,
        history: tuple[FrameVisualRow, ...] = (),
    ) -> None:
        if api_client is None:
            show_api_error("API não configurada.")
            return
        try:
            run_frame = current or api_client.open_run(card.package_id)
            frame = parse_visual_frame(run_frame.content)
        except (FletApiError, ValueError) as exc:
            show_api_error(str(exc))
            return

        def completed() -> bool:
            if run_frame.finished:
                show_story_complete(card)
                return True
            try:
                following = api_client.advance_run(
                    package_id=card.package_id,
                    frame_id=run_frame.frame_id,
                    revealed_entries=len(frame.entries),
                )
            except FletApiError as exc:
                show_api_error(str(exc))
                return False
            show_player(card, following, history=view.history_snapshot())
            return True

        def persist_reveal(_revealed_entries: int) -> bool:
            try:
                api_client.reveal_run_entry(
                    package_id=card.package_id,
                    frame_id=run_frame.frame_id,
                )
            except FletApiError as exc:
                show_api_error(str(exc))
                return False
            return True

        view = NovelFrameView(
            page,
            frame,
            image=run_frame.image_url or None,
            entry_images=run_frame.entry_image_urls,
            history=history,
            revealed_entries=run_frame.revealed_entries,
            on_frame_complete=completed,
            on_reveal=persist_reveal,
        )
        view.root.content.controls.insert(
            0,
            ft.TextButton(
                "← Voltar para os cards",
                style=ft.ButtonStyle(color="#FFFFFF"),
                on_click=lambda _event: show_library(active_cards, active_display_name),
            ),
        )
        show(view.root)
        view.focus_current()

    def show_api_error(message: str) -> None:
        page.show_dialog(ft.SnackBar(ft.Text(message)))

    def reload_library() -> None:
        if api_client is None:
            show_login()
            return
        try:
            cards = api_client.catalog()
        except FletApiError as exc:
            show_api_error(str(exc))
            return
        show_library(cards, active_display_name)

    def show_payment(card: StoryCard, state: ApiPayment | None = None) -> None:
        if api_client is None:
            show_api_error("API não configurada.")
            return
        try:
            current = state or api_client.payment_options(card.package_id)
        except FletApiError as exc:
            show_api_error(str(exc))
            return

        def run(operation) -> None:
            try:
                updated = operation()
            except FletApiError as exc:
                show_api_error(str(exc))
                return
            if updated.approved:
                reload_library()
                return
            show_payment(card, updated)

        show(
            payment_screen(
                card,
                master_test_available=current.master_test_available,
                payment_order_id=current.payment_order_id,
                qr_code=current.qr_code,
                qr_code_base64=current.qr_code_base64,
                payment_status=current.status,
                on_back=lambda: show_library(active_cards, active_display_name),
                on_create_pix=lambda: run(lambda: api_client.create_pix(card.package_id)),
                on_master_test=lambda: run(
                    lambda: api_client.approve_master_test(card.package_id)
                ),
                on_refresh=lambda: run(
                    lambda: api_client.refresh_payment(current.payment_order_id)
                ),
            )
        )

    def select_card(card: StoryCard) -> None:
        if card.access_status == AccessStatus.LOCKED:
            show_payment(card)
        else:
            show_player(card)

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
                on_open_preview=select_card,
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

        def register(
            display_name: str,
            email: str,
            password: str,
            password_confirmation: str,
        ) -> str | None:
            if api_client is None:
                return "Defina ROLEPLAY_FLET_API_URL antes de criar a conta."
            if password != password_confirmation:
                return "As senhas não coincidem."
            try:
                user = api_client.register(
                    display_name=display_name,
                    email=email,
                    password=password,
                )
                cards = api_client.catalog()
            except FletApiError as exc:
                return str(exc)
            show_library(cards, user.display_name or user.email)
            return None

        show(
            login_screen(
                on_login=authenticate,
                on_register=register,
                api_url=api_url,
            )
        )

    show_login()


if __name__ == "__main__":
    ft.run(main)
