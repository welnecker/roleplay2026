from __future__ import annotations

import flet as ft

from flet_client.frame_state import VisualEntry, VisualFrame
from flet_client.frame_view import NovelFrameView


class _Page:
    def __init__(self) -> None:
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


def _slide_image(slide: ft.Container) -> ft.Image:
    column = slide.content
    assert isinstance(column, ft.Column)
    image_container = column.controls[0]
    assert isinstance(image_container, ft.Container)
    assert isinstance(image_container.content, ft.Image)
    return image_container.content


def _slide_balloon(slide: ft.Container) -> ft.Stack:
    column = slide.content
    assert isinstance(column, ft.Column)
    balloon = column.controls[-1]
    assert isinstance(balloon, ft.Stack)
    return balloon


def test_cada_balao_forma_um_slide_com_sua_imagem_e_cauda_visivel() -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_001",
        description="Mary entra.",
        entries=(
            VisualEntry("pensamento", "mary", "Mary", "Primeiro."),
            VisualEntry("pensamento", "mary", "Mary", "Segundo."),
        ),
    )
    persisted: list[int] = []
    view = NovelFrameView(
        page,  # type: ignore[arg-type]
        frame,
        entry_images=("https://img/mary1.webp", "https://img/mary2.webp"),
        on_reveal=lambda count: persisted.append(count) is None,
    )

    assert len(view.track.controls) == 1
    first_slide = view.track.controls[0]
    assert isinstance(first_slide, ft.Container)
    assert _slide_image(first_slide).src == "https://img/mary1.webp"
    first_balloon = _slide_balloon(first_slide)
    tail = first_balloon.controls[0]
    assert isinstance(tail, ft.Container)
    assert tail.bottom == 2
    assert isinstance(tail.rotate, ft.Rotate)
    assert tail.rotate.angle > 0
    assert first_balloon.clip_behavior == ft.ClipBehavior.NONE

    view._advance()

    assert persisted == [2]
    assert len(view.track.controls) == 2
    second_slide = view.track.controls[1]
    assert isinstance(second_slide, ft.Container)
    assert _slide_image(second_slide).src == "https://img/mary2.webp"
    assert view.controller.revealed_entries == 2


def test_slides_sao_responsivos_e_carrossel_foca_o_mais_recente() -> None:
    page = _Page()
    page.width = 390
    frame = VisualFrame(
        frame_id="encontro_001",
        description="Mary entra.",
        entries=(VisualEntry("fala", "mary", "Mary", "Olá."),),
    )
    view = NovelFrameView(
        page,  # type: ignore[arg-type]
        frame,
        entry_images=("https://img/mary1.webp",),
    )

    assert view.track.auto_scroll is True
    assert view.slide_width == 338
    assert view.track.controls[0].width == 338

    view._resize(type("Resize", (), {"width": 1400})())

    assert view.slide_width == 760
    assert view.track.controls[0].width == 760


def test_revelacao_falha_restaura_o_indice_visual() -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_001",
        description="Mary entra.",
        entries=(
            VisualEntry("pensamento", "mary", "Mary", "Primeiro."),
            VisualEntry("pensamento", "mary", "Mary", "Segundo."),
        ),
    )
    view = NovelFrameView(
        page,  # type: ignore[arg-type]
        frame,
        on_reveal=lambda _count: False,
    )

    view._advance()

    assert view.controller.revealed_entries == 1
    assert view.advance_button.disabled is False
