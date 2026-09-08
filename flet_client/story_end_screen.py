from __future__ import annotations

from collections.abc import Callable

import flet as ft

from flet_client.frame_state import VisualFrame
from flet_client.screens import BACKGROUND


END_ACCENT = "#D24369"
END_CARD = "#F1B5CB"
END_TEXT = "#2B1822"


def story_end_message(frame: VisualFrame) -> str:
    """Retorna somente o texto autoral já recebido do backend."""

    if frame.entries:
        return str(frame.entries[-1].body or "").strip()
    return str(frame.description or "").strip()


def story_end_screen(
    *,
    frame: VisualFrame,
    image_url: str,
    on_return: Callable[[], None],
) -> ft.Control:
    """Despedida fixa: imagem + fala terminal + um único botão Retornar."""

    message = story_end_message(frame)
    visual: list[ft.Control] = []
    if image_url:
        visual.append(
            ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                border_radius=22,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor="#102F2D",
                content=ft.Image(
                    src=image_url,
                    fit=ft.BoxFit.CONTAIN,
                    expand=True,
                    border_radius=22,
                ),
            )
        )
    if message:
        label = frame.entries[-1].visible_name if frame.entries else ""
        visual.append(
            ft.Container(
                width=620,
                padding=20,
                border_radius=22,
                bgcolor=END_CARD,
                shadow=ft.BoxShadow(
                    blur_radius=14,
                    color="#33000000",
                    offset=ft.Offset(0, 5),
                ),
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    controls=[
                        *(
                            [
                                ft.Text(
                                    label.upper(),
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=END_TEXT,
                                )
                            ]
                            if label
                            else []
                        ),
                        ft.Text(
                            message,
                            size=18,
                            color=END_TEXT,
                            text_align=ft.TextAlign.CENTER,
                            selectable=True,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    return ft.Container(
        expand=True,
        bgcolor=BACKGROUND,
        padding=ft.Padding.symmetric(horizontal=20, vertical=18),
        content=ft.Column(
            expand=True,
            spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    "Fim da história",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    color="#FFFFFF",
                    text_align=ft.TextAlign.CENTER,
                ),
                *visual,
                ft.SafeArea(
                    content=ft.FilledButton(
                        "Retornar",
                        bgcolor=END_ACCENT,
                        color="#FFFFFF",
                        height=54,
                        on_click=lambda _event: on_return(),
                    ),
                    avoid_intrusions_left=False,
                    avoid_intrusions_top=False,
                    avoid_intrusions_right=False,
                    avoid_intrusions_bottom=True,
                    maintain_bottom_view_padding=True,
                    minimum_padding=ft.Padding.only(bottom=8),
                ),
            ],
        ),
    )


__all__ = ["story_end_message", "story_end_screen"]
