from __future__ import annotations

import math
from collections.abc import Callable

import flet as ft

from flet_client.frame_state import FrameRevealController, VisualEntry, VisualFrame


BACKGROUND = "#183D3A"
SCENE_COLOR = "#D24369"
SPEECH_COLORS = ("#ED8BAE", "#F1B5CB", "#F0CFDD", "#F3D5E6")
TEXT_COLOR = "#2B1822"


def _entry_card(entry: VisualEntry, index: int, *, width: float) -> ft.Control:
    is_thought = entry.kind == "pensamento"
    label = entry.visible_name or entry.actor or "Personagem"
    card_color = "#F7DFEA" if is_thought else SPEECH_COLORS[index % len(SPEECH_COLORS)]
    border = ft.Border.all(2, "#8F6475") if is_thought else None
    card = ft.Container(
        width=width,
        margin=ft.Margin.only(left=11, right=11, bottom=14),
        padding=18,
        border_radius=22,
        bgcolor=card_color,
        border=border,
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
        width=24,
        height=24,
        left=None if tail_on_right else 42,
        right=42 if tail_on_right else None,
        bottom=2,
        bgcolor=card_color,
        border=border,
        rotate=ft.Rotate(angle=math.pi / 4),
    )
    return ft.Stack(
        controls=[tail, card],
        width=width + 22,
        clip_behavior=ft.ClipBehavior.NONE,
    )


def _slide_width(viewport_width: float | None) -> float:
    """Replica o contrato do carrossel: tela cheia no mobile e faixa no desktop."""

    width = float(viewport_width or 390)
    usable = max(280.0, width - 52.0)
    if width < 900:
        return min(usable, 720.0)
    return min(760.0, max(420.0, width * 0.72))


def _image_height(slide_width: float) -> float:
    return min(460.0, max(230.0, slide_width * 0.58))


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
        self.slide_width = _slide_width(getattr(page, "width", None))
        self.track = ft.Row(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )
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
            on_size_change=self._resize,
        )
        self._refresh(update_page=False)

    def _entry_image(self, index: int) -> bytes | str | None:
        """Retorna a imagem efetiva da entry, carregando a última válida."""

        active: bytes | str | None = self.base_image
        for position in range(index + 1):
            if position < len(self.entry_images) and self.entry_images[position]:
                active = self.entry_images[position]
        return active

    def _entry_slide(self, entry: VisualEntry, index: int) -> ft.Control:
        image = self._entry_image(index)
        controls: list[ft.Control] = []
        if image:
            controls.append(
                ft.Container(
                    width=self.slide_width,
                    height=_image_height(self.slide_width),
                    alignment=ft.Alignment.CENTER,
                    border_radius=18,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    bgcolor="#102F2D",
                    content=ft.Image(
                        src=image,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=18,
                        expand=True,
                    ),
                )
            )
        controls.append(
            _entry_card(
                entry,
                index,
                width=max(258.0, self.slide_width - 22.0),
            )
        )
        return ft.Container(
            key=f"frame-slide-{self.controller.frame.frame_id}-{index}",
            width=self.slide_width,
            content=ft.Column(
                controls=controls,
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _resize(self, event: object) -> None:
        width = getattr(event, "width", None)
        next_width = _slide_width(width)
        if abs(next_width - self.slide_width) < 1:
            return
        self.slide_width = next_width
        self._refresh()

    def _refresh(self, *, update_page: bool = True) -> None:
        self.track.controls = [
            self._entry_slide(entry, index)
            for index, entry in enumerate(self.controller.visible_entries)
        ]
        total = len(self.controller.frame.entries)
        self.progress.value = f"{self.controller.revealed_entries} de {total}"
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
