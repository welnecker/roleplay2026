from __future__ import annotations

from collections.abc import Callable, Sequence

import flet as ft

from platform_core.models import AccessStatus, StoryCard


BACKGROUND = "#143936"
SURFACE = "#F9F2F5"
SURFACE_MUTED = "#EEDDE5"
ACCENT = "#D24369"
ACCENT_DARK = "#A52D50"
INK = "#2B1822"
MUTED = "#765E68"


def flet_image_source(source: str) -> str:
    """Remove o cabeçalho data URL e entrega Base64 puro ao Flet desktop."""

    value = str(source or "").strip()
    if not value.startswith("data:image/") or ";base64," not in value:
        return value
    _header, encoded = value.split(",", maxsplit=1)
    return encoded.strip()


def _logo() -> ft.Column:
    return ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=2,
        controls=[
            ft.Text("ENTRE", size=13, weight=ft.FontWeight.BOLD, color="#FFFFFFAA"),
            ft.Text("CENAS", size=34, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ft.Container(width=52, height=3, bgcolor=ACCENT, border_radius=2),
        ],
    )


def login_screen(*, on_preview_login: Callable[[], None]) -> ft.Control:
    email = ft.TextField(
        label="E-mail",
        hint_text="voce@email.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        border_radius=14,
        autofocus=True,
    )
    password = ft.TextField(
        label="Senha",
        password=True,
        can_reveal_password=True,
        border_radius=14,
    )

    return ft.Container(
        expand=True,
        bgcolor=BACKGROUND,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=22, vertical=30),
        content=ft.Column(
            tight=True,
            width=430,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=22,
            controls=[
                _logo(),
                ft.Container(
                    bgcolor=SURFACE,
                    border_radius=26,
                    padding=ft.Padding.symmetric(horizontal=28, vertical=26),
                    shadow=ft.BoxShadow(
                        blur_radius=28,
                        color="#50000000",
                        offset=ft.Offset(0, 10),
                    ),
                    content=ft.Column(
                        spacing=17,
                        controls=[
                            ft.Text("Bem-vindo de volta", size=25, weight=ft.FontWeight.BOLD, color=INK),
                            ft.Text(
                                "Entre para continuar suas histórias.",
                                size=14,
                                color=MUTED,
                            ),
                            email,
                            password,
                            ft.FilledButton(
                                "Entrar na prévia visual",
                                height=52,
                                bgcolor=ACCENT,
                                color="#FFFFFF",
                                on_click=lambda _event: on_preview_login(),
                            ),
                            ft.TextButton(
                                "Esqueci minha senha",
                                disabled=True,
                            ),
                        ],
                    ),
                ),
                ft.Container(
                    border=ft.Border.all(1, "#FFFFFF33"),
                    border_radius=12,
                    padding=12,
                    content=ft.Text(
                        "PRÉVIA LOCAL · Os campos não são enviados. O login real será conectado à API autenticada.",
                        size=11,
                        text_align=ft.TextAlign.CENTER,
                        color="#FFFFFFBB",
                    ),
                ),
            ],
        ),
    )


def _status(card: StoryCard) -> tuple[str, str]:
    if card.access_status == AccessStatus.FREE:
        return "DEGUSTAÇÃO", "#3D8068"
    if card.access_status == AccessStatus.OWNED:
        return "LIBERADO", "#3D8068"
    return card.price_label or "BLOQUEADO", ACCENT_DARK


def _story_card(card: StoryCard, *, on_open_preview: Callable[[StoryCard], None]) -> ft.Control:
    status_label, status_color = _status(card)
    cover: ft.Control
    if card.cover_url:
        cover = ft.Image(
            src=flet_image_source(card.cover_url),
            fit=ft.BoxFit.COVER,
            left=0,
            top=0,
            right=0,
            bottom=0,
        )
    else:
        cover = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            bgcolor=SURFACE_MUTED,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.IMAGE_OUTLINED, size=46, color=MUTED),
        )

    return ft.Container(
        col={"xs": 12, "sm": 6, "lg": 4, "xl": 3},
        bgcolor=SURFACE,
        border_radius=22,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=ft.BoxShadow(blur_radius=18, color="#35000000", offset=ft.Offset(0, 7)),
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Stack(
                    height=280,
                    fit=ft.StackFit.EXPAND,
                    controls=[
                        cover,
                        ft.Container(
                            top=14,
                            right=14,
                            bgcolor=status_color,
                            border_radius=20,
                            padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                            content=ft.Text(
                                status_label,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color="#FFFFFF",
                            ),
                        ),
                    ]
                ),
                ft.Container(
                    padding=20,
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Text(card.title, size=23, weight=ft.FontWeight.BOLD, color=INK),
                            ft.Text(card.subtitle, size=14, color=MUTED, max_lines=3),
                            ft.Row(
                                spacing=7,
                                controls=[
                                    ft.Container(
                                        bgcolor=SURFACE_MUTED,
                                        border_radius=12,
                                        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                                        content=ft.Text(genre, size=10, color=INK),
                                    )
                                    for genre in card.genres[:2]
                                ],
                            ),
                            ft.FilledButton(
                                "Abrir demonstração",
                                bgcolor=ACCENT,
                                color="#FFFFFF",
                                height=45,
                                on_click=lambda _event, selected=card: on_open_preview(selected),
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )


def library_screen(
    cards: Sequence[StoryCard],
    *,
    display_name: str,
    on_logout: Callable[[], None],
    on_open_preview: Callable[[StoryCard], None],
) -> ft.Control:
    return ft.Container(
        expand=True,
        bgcolor=BACKGROUND,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=22, vertical=17),
                    bgcolor="#102E2C",
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("ENTRE CENAS", size=19, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Text(f"Olá, {display_name}", size=13, color="#FFFFFFCC"),
                                    ft.IconButton(
                                        icon=ft.Icons.LOGOUT,
                                        icon_color="#FFFFFF",
                                        tooltip="Sair da prévia",
                                        on_click=lambda _event: on_logout(),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=22, vertical=24),
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=20,
                        controls=[
                            ft.Column(
                                spacing=5,
                                controls=[
                                    ft.Text("Aprecie sem moderação", size=30, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    ft.Text(
                                        "Escolha uma história e mergulhe na experiência.",
                                        size=14,
                                        color="#FFFFFFBB",
                                    ),
                                ],
                            ),
                            ft.ResponsiveRow(
                                spacing=18,
                                run_spacing=18,
                                controls=[
                                    _story_card(card, on_open_preview=on_open_preview)
                                    for card in cards
                                ],
                            ),
                            ft.Container(height=12),
                        ],
                    ),
                ),
            ],
        ),
    )


__all__ = ["BACKGROUND", "flet_image_source", "library_screen", "login_screen"]
