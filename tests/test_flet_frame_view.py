from __future__ import annotations

import flet as ft

from flet_client.frame_state import VisualEntry, VisualFrame
from flet_client.frame_view import NovelFrameView


class _Page:
    def __init__(self) -> None:
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


def test_baloes_tem_cauda_e_imagem_acompanha_revelacao() -> None:
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

    assert view.image_control.src == "https://img/mary1.webp"
    first_balloon = view.track.controls[0]
    assert isinstance(first_balloon, ft.Stack)
    assert any(
        isinstance(control, ft.Container) and control.rotate is not None
        for control in first_balloon.controls
    )

    view._advance()

    assert persisted == [2]
    assert view.image_control.src == "https://img/mary2.webp"
    assert view.controller.revealed_entries == 2


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
