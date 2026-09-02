from __future__ import annotations

import os
import flet as ft

from flet_client.api_client import ApiPayment, ApiRunFrame, FletApiClient, FletApiError
from flet_client.auth_storage import AuthTokenStorage
from flet_client.frame_state import parse_visual_frame
from flet_client.frame_view import FrameVisualRow, NovelFrameView
from flet_client.models import AccessStatus, StoryCard
from flet_client.screens import BACKGROUND, library_screen, login_screen, payment_screen
from flet_client.story_end_screen import story_end_screen

DEFAULT_FLET_API_URL = "https://entrecenas-roleplay.com.br"


def configured_api_url() -> str:
    return os.getenv("ROLEPLAY_FLET_API_URL", DEFAULT_FLET_API_URL).strip().rstrip("/")


async def main(page: ft.Page) -> None:
    page.title = "EntreCenas"
    page.bgcolor = BACKGROUND
    page.padding = 0
    page.theme_mode = ft.ThemeMode.LIGHT
    api_url = configured_api_url()
    api_client = FletApiClient(api_url) if api_url else None
    token_storage = AuthTokenStorage()
    active_cards: list[StoryCard] = []
    active_display_name = ""

    def show(control: ft.Control) -> None:
        page.controls.clear()
        page.add(control)
        page.update()

    def show_api_error(message: str) -> None:
        page.show_dialog(ft.SnackBar(ft.Text(message)))

    async def persist_current_token() -> None:
        if api_client is None or not api_client.access_token:
            return
        try:
            await token_storage.set_token(api_client.access_token)
        except Exception:
            # Falha do cofre local não invalida uma sessão já autenticada.
            pass

    async def clear_local_auth(*, revoke_server: bool) -> None:
        if api_client is not None:
            if revoke_server:
                try:
                    api_client.logout()
                except FletApiError:
                    api_client.access_token = ""
            else:
                api_client.access_token = ""
        try:
            await token_storage.clear_token()
        except Exception:
            pass

    async def authentication_failed() -> None:
        await clear_local_auth(revoke_server=False)
        show_login()

    def handle_api_error(exc: FletApiError) -> None:
        if exc.is_authentication_error:
            page.run_task(authentication_failed)
            return
        show_api_error(str(exc))

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
        except FletApiError as exc:
            handle_api_error(exc)
            return
        except ValueError as exc:
            show_api_error(str(exc))
            return

        # Um quadro terminal determinístico já chega completamente concluído.
        # Mantemos imagem e despedida fixas e oferecemos somente Retornar; nenhum
        # advance/reveal adicional é necessário depois desse ponto.
        if run_frame.finished:
            show(
                story_end_screen(
                    frame=frame,
                    image_url=run_frame.image_url,
                    on_return=reload_library,
                )
            )
            return

        def completed() -> bool:
            if run_frame.finished:
                reload_library()
                return True
            try:
                following = api_client.advance_run(
                    package_id=card.package_id,
                    frame_id=run_frame.frame_id,
                    revealed_entries=len(frame.entries),
                )
            except FletApiError as exc:
                handle_api_error(exc)
                return False
            show_player(card, following, history=view.history_snapshot())
            return True

        def persist_reveal(_revealed_entries: int) -> bool:
            nonlocal run_frame
            try:
                # O backend pode marcar finished=True exatamente na última
                # revelação. Guarde a resposta para completed() enxergar esse
                # estado e não disparar um advance extra.
                run_frame = api_client.reveal_run_entry(
                    package_id=card.package_id,
                    frame_id=run_frame.frame_id,
                )
            except FletApiError as exc:
                handle_api_error(exc)
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

    def reload_library() -> None:
        if api_client is None:
            show_login()
            return
        try:
            cards = api_client.catalog()
        except FletApiError as exc:
            handle_api_error(exc)
            return
        show_library(cards, active_display_name)

    def show_payment(card: StoryCard, state: ApiPayment | None = None) -> None:
        if api_client is None:
            show_api_error("API não configurada.")
            return
        try:
            current = state or api_client.payment_options(card.package_id)
        except FletApiError as exc:
            handle_api_error(exc)
            return

        def run(operation) -> None:
            try:
                updated = operation()
            except FletApiError as exc:
                handle_api_error(exc)
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

        async def logout_flow() -> None:
            await clear_local_auth(revoke_server=True)
            show_login()

        def logout() -> None:
            page.run_task(logout_flow)

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
            page.run_task(persist_current_token)
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
            page.run_task(persist_current_token)
            show_library(cards, user.display_name or user.email)
            return None

        show(
            login_screen(
                on_login=authenticate,
                on_register=register,
                api_url=api_url,
            )
        )

    async def restore_session() -> None:
        if api_client is None:
            show_login()
            return
        try:
            token = await token_storage.get_token()
        except Exception:
            token = ""
        if not token:
            show_login()
            return

        api_client.access_token = token
        try:
            user = api_client.me()
            cards = api_client.catalog()
        except FletApiError as exc:
            if exc.is_authentication_error:
                await clear_local_auth(revoke_server=False)
                show_login()
                return

            # Rede/Sheets/5xx não significam logout. Mantenha o token e dê ao
            # usuário uma forma explícita de tentar novamente ou sair.
            show(
                ft.Container(
                    expand=True,
                    bgcolor=BACKGROUND,
                    alignment=ft.Alignment.CENTER,
                    padding=32,
                    content=ft.Column(
                        tight=True,
                        spacing=16,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "Não foi possível restaurar sua sessão agora.",
                                size=20,
                                color="#FFFFFF",
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                str(exc),
                                color="#D6E5E3",
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.FilledButton(
                                "Tentar novamente",
                                on_click=lambda _event: page.run_task(restore_session),
                            ),
                            ft.TextButton(
                                "Sair desta conta",
                                on_click=lambda _event: page.run_task(authentication_failed),
                            ),
                        ],
                    ),
                )
            )
            return

        show_library(cards, user.display_name or user.email)

    await restore_session()


if __name__ == "__main__":
    ft.run(main)
