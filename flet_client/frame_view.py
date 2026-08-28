from __future__ import annotations

import math
from collections.abc import Callable

import flet as ft

from flet_client.frame_state import FrameRevealController, VisualEntry, VisualFrame


BACKGROUND = "#183D3A"
SCENE_COLOR = "#D24369"
SPEECH_COLORS = ("#ED8BAE", "#F1B5CB", "#F0CFDD", "#F3D5E6")
TEXT_COLOR = "#2B1822"


def _entry_card(entry: VisualEntry, index: int) -> ft.Control:
    is_thought = entry.kind == "pensamento"
    label = entry.visible_name or entry.actor or "Personagem"
    card_color = "#F7DFEA" if is_thought else SPEECH_COLORS[index % len(SPEECH_COLORS)]
    card = ft.Container(
        width=360,
        margin=ft.Margin.only(left=11, right=11),
        padding=18,
        border_radius=22,
        bgcolor=card_color,
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
    tail_on_right = index % 2 == 1
    tail = ft.Container(
        width=23,
        height=23,
        left=None if tail_on_right else 1,
        right=1 if tail_on_right else None,
        top=38,
        bgcolor=card_color,
        border=ft.Border.all(2, "#8F6475") if is_thought else None,
        rotate=ft.Rotate(angle=math.pi / 4),
    )
    return ft.Stack(
        controls=[tail, card],
        width=382,
        clip_behavior=ft.ClipBehavior.NONE,
    )


class NovelFrameView:
    """Player visual de um quadro; não contém regras de backend ou cobrança."""

    def __init__(
        self,
        page: ft.Page,
        frame: VisualFrame,
        *,
        image: bytes | str | None = None,
        entry_images: tuple[str, ...] = (),
        revealed_entries: int = 0,
        on_frame_complete: Callable[[], bool] | None = None,
        on_reveal: Callable[[int], bool] | None = None,
    ) -> None:
        self.page = page
        self.controller = FrameRevealController(
            frame,
            revealed_entries=revealed_entries,
        )
        self.on_frame_complete = on_frame_complete
        self.on_reveal = on_reveal
        self.base_image = image
        self.entry_images = tuple(entry_images)
        self._busy = False
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
        self.image_control = ft.Image(
            src=image or "",
            fit=ft.BoxFit.CONTAIN,
            border_radius=18,
            expand=True,
        )
        self.image_container = ft.Container(
            height=420,
            alignment=ft.Alignment.CENTER,
            border_radius=18,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=self.image_control,
            visible=bool(image or any(self.entry_images)),
        )
        if self.image_container.visible:
            controls.append(
                self.image_container
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
        image_index = max(0, self.controller.revealed_entries - 1)
        active_image = (
            self.entry_images[image_index]
            if image_index < len(self.entry_images) and self.entry_images[image_index]
            else self.base_image or ""
        )
        self.image_control.src = active_image
        self.image_container.visible = bool(active_image)
        self.advance_button.disabled = self._busy
        self.advance_button.content = (
            "Carregando..."
            if self._busy
            else "Próximo quadro"
            if self.controller.all_entries_visible
            else "Revelar próximo balão"
        )
        if update_page:
            self.page.update()

    def _advance(self, _event: object = None) -> None:
        if self._busy:
            return
        if self.controller.advance():
            self._busy = True
            self._refresh()
            if self.on_frame_complete is not None:
                if self.on_frame_complete():
                    return
            self._busy = False
            self._refresh()
            return
        previous = self.controller.revealed_entries - 1
        self._busy = True
        self._refresh()
        if self.on_reveal is not None:
            if not self.on_reveal(self.controller.revealed_entries):
                self.controller.revealed_entries = previous
        self._busy = False
        self._refresh()
