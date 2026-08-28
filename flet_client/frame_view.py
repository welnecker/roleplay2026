from __future__ import annotations

from collections.abc import Callable

import flet as ft

from flet_client.frame_state import FrameRevealController, VisualEntry, VisualFrame


BACKGROUND = "#183D3A"
SCENE_COLOR = "#D24369"
SPEECH_COLORS = ("#ED8BAE", "#F1B5CB", "#F0CFDD", "#F3D5E6")
TEXT_COLOR = "#2B1822"


def _entry_card(entry: VisualEntry, index: int) -> ft.Container:
    is_thought = entry.kind == "pensamento"
    label = entry.visible_name or entry.actor or "Personagem"
    return ft.Container(
        width=360,
        padding=18,
        border_radius=22,
        bgcolor="#F7DFEA" if is_thought else SPEECH_COLORS[index % len(SPEECH_COLORS)],
        border=ft.Border.all(2, "#8F6475") if is_thought else None,
        shadow=ft.BoxShadow(blur_radius=14, color="#33000000", offset=ft.Offset(0, 5)),
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Text(
                    f"✦ pensamento · {label}" if is_thought else label.upper(),
                    size=12,
                    weight=ft.FontWeight.BOLD,
                    color="#755363" if is_thought else TEXT_COLOR,
                ),
                ft.Text(
                    entry.body,
                    size=17,
                    italic=is_thought,
                    color=TEXT_COLOR,
                    selectable=True,
                ),
            ],
        ),
    )


class NovelFrameView:
    """Player visual de um quadro; não contém regras de backend ou cobrança."""

    def __init__(
        self,
        page: ft.Page,
        frame: VisualFrame,
        *,
        image: bytes | str | None = None,
        revealed_entries: int = 0,
        on_frame_complete: Callable[[], None] | None = None,
        on_reveal: Callable[[int], None] | None = None,
    ) -> None:
        self.page = page
        self.controller = FrameRevealController(
            frame,
            revealed_entries=revealed_entries,
        )
        self.on_frame_complete = on_frame_complete
        self.on_reveal = on_reveal
        self.track = ft.Row(spacing=14, scroll=ft.ScrollMode.AUTO)
        self.progress = ft.Text(size=12, color="#D6E5E3")
        self.advance_button = ft.FilledButton(
            "Avançar",
            bgcolor=SCENE_COLOR,
            color="#FFFFFF",
            height=52,
            on_click=self._advance,
        )

        controls: list[ft.Control] = [
            ft.Container(
                padding=18,
                border_radius=16,
                bgcolor=SCENE_COLOR,
                content=ft.Column(
                    spacing=8,
                    controls=[
                        ft.Text("CENA", size=12, weight=ft.FontWeight.BOLD, color="#FFFFFFCC"),
                        ft.Text(frame.description, size=17, color="#FFFFFF", selectable=True),
                    ],
                ),
            )
        ]
        if image:
            controls.append(
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    border_radius=18,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    content=ft.Image(
                        src=image,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=18,
                    ),
                )
            )
        controls.extend(
            [
                self.track,
                ft.Row([self.progress, self.advance_button], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ]
        )
        self.root = ft.Container(
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            bgcolor=BACKGROUND,
            content=ft.Column(
                controls=controls,
                spacing=14,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
            expand=True,
        )
        self._refresh(update_page=False)

    def _refresh(self, *, update_page: bool = True) -> None:
        self.track.controls = [
            _entry_card(entry, index)
            for index, entry in enumerate(self.controller.visible_entries)
        ]
        total = len(self.controller.frame.entries)
        self.progress.value = f"{self.controller.revealed_entries} de {total}"
        self.advance_button.content = (
            "Próximo quadro" if self.controller.all_entries_visible else "Revelar próximo balão"
        )
        if update_page:
            self.page.update()

    def _advance(self, _event: object = None) -> None:
        if self.controller.advance():
            if self.on_frame_complete is not None:
                self.on_frame_complete()
            return
        if self.on_reveal is not None:
            self.on_reveal(self.controller.revealed_entries)
        self._refresh()
