from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import flet as ft

from flet_client.frame_state import FrameRevealController, VisualEntry, VisualFrame


BACKGROUND = "#183D3A"
SCENE_COLOR = "#D24369"
SPEECH_COLORS = ("#ED8BAE", "#F1B5CB", "#F0CFDD", "#F3D5E6")
TEXT_COLOR = "#2B1822"
INTERACTION_LIMIT = 5


@dataclass(frozen=True, slots=True)
class FrameVisualItem:
    frame_id: str
    entry_index: int
    entry: VisualEntry | None
    image: bytes | str | None


@dataclass(frozen=True, slots=True)
class FrameVisualRow:
    frame_id: str
    items: tuple[FrameVisualItem, ...]


@dataclass(slots=True)
class FrameStageCursor:
    """Cursor puramente visual sobre posições já reveladas do quadro.

    Ele nunca altera ``revealed_entries``. Assim voltar/avançar na revisão não
    desfaz progresso, não escreve no Sheets e não consome uma nova interação.
    """

    position: int = 0

    def clamp(self, item_count: int) -> int:
        maximum = max(0, int(item_count) - 1)
        self.position = min(max(0, int(self.position)), maximum)
        return self.position

    def latest(self, item_count: int) -> int:
        self.position = max(0, int(item_count) - 1)
        return self.position

    def previous(self, item_count: int) -> int:
        self.clamp(item_count)
        self.position = max(0, self.position - 1)
        return self.position

    def next(self, item_count: int) -> int:
        maximum = max(0, int(item_count) - 1)
        self.clamp(item_count)
        self.position = min(maximum, self.position + 1)
        return self.position


def _entry_card(entry: VisualEntry, index: int, *, width: float) -> ft.Control:
    is_thought = entry.kind == "pensamento"
    is_impact_balloon = not is_thought and entry.impact_balloon
    label = entry.visible_name or entry.actor or "Personagem"
    card_color = "#F7DFEA" if is_thought else SPEECH_COLORS[index % len(SPEECH_COLORS)]
    border = ft.Border.all(2, "#8F6475") if is_thought else None
    card = ft.Container(
        width=width,
        margin=ft.Margin.only(left=11, right=11, top=18),
        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
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
                    size=23 if is_impact_balloon else 17,
                    weight=ft.FontWeight.BOLD if is_impact_balloon else None,
                    italic=is_thought,
                    color=TEXT_COLOR,
                    selectable=True,
                ),
            ],
        ),
    )
    # O balão permanece abaixo da imagem e sua cauda aponta para cima.
    if is_thought:
        tails: list[ft.Control] = [
            ft.Container(
                width=size,
                height=size,
                left=38 + offset,
                top=top,
                bgcolor=card_color,
                border=border,
                shape=ft.BoxShape.CIRCLE,
            )
            for size, offset, top in ((7, 0, 0), (11, 8, 5), (16, 18, 10))
        ]
    else:
        tails = [
            ft.Container(
                width=24,
                height=24,
                left=44,
                top=5,
                bgcolor=card_color,
                border=border,
                rotate=ft.Rotate(angle=math.pi / 4),
            )
        ]
    return ft.Stack(
        controls=[*tails, card],
        width=width + 22,
        clip_behavior=ft.ClipBehavior.NONE,
    )


def _stage_width(viewport_width: float | None) -> float:
    width = float(viewport_width or 390)
    usable = max(300.0, width - 48.0)
    if width >= 1200:
        return min(1080.0, usable)
    if width >= 760:
        return min(900.0, usable)
    return usable


def _image_height(stage_width: float, viewport_width: float | None) -> float:
    width = float(viewport_width or 390)
    if width >= 1200:
        return min(610.0, max(390.0, stage_width * 0.56))
    if width >= 760:
        return min(520.0, max(330.0, stage_width * 0.56))
    return min(360.0, max(220.0, stage_width * 0.62))


def _balloon_width(stage_width: float, viewport_width: float | None) -> float:
    width = float(viewport_width or 390)
    ratio = 0.72 if width >= 1000 else 0.9 if width >= 620 else 0.96
    return max(270.0, min(stage_width, stage_width * ratio))


class NovelFrameView:
    """Player visual focado: uma imagem grande e um balão por vez."""

    def __init__(
        self,
        page: ft.Page,
        frame: VisualFrame,
        *,
        image: bytes | str | None = None,
        entry_images: tuple[str, ...] = (),
        history: tuple[FrameVisualRow, ...] = (),
        revealed_entries: int = 0,
        on_frame_complete: Callable[[], bool] | None = None,
        on_reveal: Callable[[int], bool] | None = None,
    ) -> None:
        self.page = page
        self.controller = FrameRevealController(frame, revealed_entries=revealed_entries)
        self.on_frame_complete = on_frame_complete
        self.on_reveal = on_reveal
        self.base_image = image
        self.entry_images = tuple(entry_images)
        self.history = tuple(history[-(INTERACTION_LIMIT - 1) :])
        self._busy = False
        self._viewport_width = float(getattr(page, "width", None) or 390)
        self.stage_width = _stage_width(self._viewport_width)
        self.stage_cursor = FrameStageCursor()

        self.scene_description = ft.Text(
            frame.description,
            size=17,
            color="#FFFFFF",
            selectable=True,
        )
        self.stage = ft.Container(alignment=ft.Alignment.TOP_CENTER, expand=True)
        self.position_indicator = ft.Text(size=13, color="#D6E5E3")
        self.previous_button = ft.OutlinedButton(
            "← Anterior",
            on_click=self._review_previous,
            style=ft.ButtonStyle(color="#FFFFFF"),
        )
        self.review_next_button = ft.OutlinedButton(
            "Seguinte →",
            on_click=self._review_next,
            style=ft.ButtonStyle(color="#FFFFFF"),
        )
        self.progress = ft.Text(size=12, color="#D6E5E3")
        self.advance_button = ft.FilledButton(
            "Avançar",
            bgcolor=SCENE_COLOR,
            color="#FFFFFF",
            height=52,
            on_click=self._advance,
        )

        self.root = ft.Container(
            padding=ft.Padding.symmetric(horizontal=18, vertical=14),
            bgcolor=BACKGROUND,
            content=ft.Column(
                controls=[
                    ft.Container(
                        padding=18,
                        border_radius=16,
                        bgcolor=SCENE_COLOR,
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                ft.Text(
                                    "CENA",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FFFFFFCC",
                                ),
                                self.scene_description,
                            ],
                        ),
                    ),
                    self.stage,
                    ft.Row(
                        [
                            self.previous_button,
                            self.position_indicator,
                            self.review_next_button,
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=14,
                    ),
                    ft.SafeArea(
                        content=ft.Row(
                            [self.progress, self.advance_button],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        avoid_intrusions_left=False,
                        avoid_intrusions_top=False,
                        avoid_intrusions_right=False,
                        avoid_intrusions_bottom=True,
                        maintain_bottom_view_padding=True,
                        minimum_padding=ft.Padding.only(bottom=8),
                    ),
                ],
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            expand=True,
            on_size_change=self._resize,
        )
        self.stage_cursor.latest(len(self._current_row().items))
        self._refresh(update_page=False)

    def _entry_image(self, index: int) -> bytes | str | None:
        """Retorna a imagem efetiva da entry, carregando a última válida."""

        active: bytes | str | None = self.base_image
        for position in range(index + 1):
            if position < len(self.entry_images) and self.entry_images[position]:
                active = self.entry_images[position]
        return active

    def _current_row(self) -> FrameVisualRow:
        items = [
            FrameVisualItem(
                frame_id=self.controller.frame.frame_id,
                entry_index=index,
                entry=entry,
                image=self._entry_image(index),
            )
            for index, entry in enumerate(self.controller.visible_entries)
        ]
        # Quando a primeira fala troca imediatamente a imagem, preserve a imagem
        # autoral da [DESCRIÇÃO] como a primeira posição visual do quadro.
        first_entry_image = items[0].image if items else None
        if self.base_image and first_entry_image != self.base_image:
            items.insert(
                0,
                FrameVisualItem(
                    frame_id=self.controller.frame.frame_id,
                    entry_index=-1,
                    entry=None,
                    image=self.base_image,
                ),
            )
        return FrameVisualRow(self.controller.frame.frame_id, tuple(items))

    def _visible_rows(self) -> tuple[FrameVisualRow, ...]:
        # O histórico continua sendo transportado entre quadros para compatibilidade
        # e eventual revisão futura, mas o palco principal mostra somente o quadro
        # atual para não poluir o desktop.
        return self.history + (self._current_row(),)

    def history_snapshot(
        self,
        *,
        limit: int = INTERACTION_LIMIT,
    ) -> tuple[FrameVisualRow, ...]:
        return self._visible_rows()[-max(1, int(limit)) :]

    def _selected_item(self) -> FrameVisualItem | None:
        items = self._current_row().items
        if not items:
            return None
        index = self.stage_cursor.clamp(len(items))
        return items[index]

    def _stage_control(self, item: FrameVisualItem | None) -> ft.Control:
        if item is None:
            return ft.Container(
                width=self.stage_width,
                alignment=ft.Alignment.CENTER,
                content=ft.Text("Cena sem conteúdo visual.", color="#D6E5E3"),
            )

        controls: list[ft.Control] = []
        if item.image:
            controls.append(
                ft.Container(
                    width=self.stage_width,
                    height=_image_height(self.stage_width, self._viewport_width),
                    alignment=ft.Alignment.CENTER,
                    border_radius=20,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    bgcolor="#102F2D",
                    content=ft.Image(
                        src=item.image,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=20,
                        expand=True,
                    ),
                )
            )
        if item.entry is not None:
            controls.append(
                _entry_card(
                    item.entry,
                    max(0, item.entry_index),
                    width=_balloon_width(self.stage_width, self._viewport_width),
                )
            )
        return ft.Container(
            width=self.stage_width,
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Column(
                controls=controls,
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def focus_current(self) -> None:
        """Compatibilidade com o chamador; o novo palco já nasce focado."""

        return None

    def _resize(self, event: object) -> None:
        width = float(getattr(event, "width", None) or self._viewport_width)
        next_width = _stage_width(width)
        if abs(next_width - self.stage_width) < 1 and abs(width - self._viewport_width) < 1:
            return
        self._viewport_width = width
        self.stage_width = next_width
        self._refresh()

    def _review_previous(self, _event: object = None) -> None:
        items = self._current_row().items
        self.stage_cursor.previous(len(items))
        self._refresh()

    def _review_next(self, _event: object = None) -> None:
        items = self._current_row().items
        self.stage_cursor.next(len(items))
        self._refresh()

    def _refresh(self, *, update_page: bool = True) -> None:
        items = self._current_row().items
        self.stage_cursor.clamp(len(items))
        self.stage.content = self._stage_control(self._selected_item())

        item_count = len(items)
        current_position = self.stage_cursor.position + 1 if item_count else 0
        dots = " ".join(
            "●" if index == self.stage_cursor.position else "○"
            for index in range(item_count)
        )
        self.position_indicator.value = (
            f"{dots}  {current_position}/{item_count}" if item_count else ""
        )
        self.previous_button.disabled = self._busy or item_count <= 1 or self.stage_cursor.position <= 0
        self.review_next_button.disabled = (
            self._busy
            or item_count <= 1
            or self.stage_cursor.position >= item_count - 1
        )

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

        previous_revealed = self.controller.revealed_entries - 1
        self._busy = True
        self._refresh()
        if self.on_reveal is not None:
            if not self.on_reveal(self.controller.revealed_entries):
                self.controller.revealed_entries = previous_revealed
        self._busy = False
        # Uma revelação nova sempre leva o palco ao conteúdo mais recente. O
        # usuário pode depois voltar localmente sem qualquer chamada à API.
        self.stage_cursor.latest(len(self._current_row().items))
        self._refresh()
