from __future__ import annotations

import asyncio

import flet as ft
import pytest

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


def _interaction_slides(view: NovelFrameView, index: int = 0) -> list[ft.Control]:
    wrapper = view.track.controls[index]
    assert isinstance(wrapper, ft.Container)
    row = wrapper.content
    assert isinstance(row, ft.Row)
    return row.controls


def test_cada_balao_forma_um_slide_com_sua_imagem_e_cauda_visivel() -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_001",
        description="Mary entra.",
        entries=(
            VisualEntry("pensamento", "mary", "Mary", "Primeiro."),
            VisualEntry("fala", "mary", "Mary", "Segundo."),
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
    assert len(_interaction_slides(view)) == 1
    first_slide = _interaction_slides(view)[0]
    assert isinstance(first_slide, ft.Container)
    assert _slide_image(first_slide).src == "https://img/mary1.webp"
    first_balloon = _slide_balloon(first_slide)
    thought_tails = first_balloon.controls[:-1]
    assert len(thought_tails) == 3
    assert all(
        isinstance(tail, ft.Container)
        and tail.shape == ft.BoxShape.CIRCLE
        and tail.top is not None
        and tail.top >= 0
        for tail in thought_tails
    )
    assert first_balloon.clip_behavior == ft.ClipBehavior.NONE

    view._advance()

    assert persisted == [2]
    assert len(view.track.controls) == 1
    assert len(_interaction_slides(view)) == 2
    second_slide = _interaction_slides(view)[1]
    assert isinstance(second_slide, ft.Container)
    assert _slide_image(second_slide).src == "https://img/mary2.webp"
    speech_balloon = _slide_balloon(second_slide)
    speech_tail = speech_balloon.controls[0]
    assert isinstance(speech_tail, ft.Container)
    assert speech_tail.top == 5
    assert isinstance(speech_tail.rotate, ft.Rotate)
    assert view.controller.revealed_entries == 2


def test_linha_e_responsiva_e_tem_barra_para_rever_as_imagens() -> None:
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

    assert isinstance(view.track, ft.Column)
    assert view.track.scroll == ft.ScrollMode.ALWAYS
    assert view.track.auto_scroll is False
    assert view.slide_width == pytest.approx(317.72)
    first_row = view.track.controls[0].content
    assert isinstance(first_row, ft.Row)
    assert first_row.scroll == ft.ScrollMode.ALWAYS
    assert first_row.auto_scroll is False
    assert first_row.controls[0].width == pytest.approx(317.72)

    view._resize(type("Resize", (), {"width": 1400})())

    assert view.slide_width == 326.5
    assert _interaction_slides(view)[0].width == 326.5


def test_controles_respeitam_a_area_segura_inferior_do_android() -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_001",
        description="Mary entra.",
        entries=(VisualEntry("fala", "mary", "Mary", "Olá."),),
    )
    view = NovelFrameView(page, frame)  # type: ignore[arg-type]

    layout = view.root.content
    assert isinstance(layout, ft.Column)
    footer = layout.controls[-1]
    assert isinstance(footer, ft.SafeArea)
    assert footer.avoid_intrusions_bottom is True
    assert footer.maintain_bottom_view_padding is True
    assert footer.minimum_padding == ft.Padding.only(bottom=8)


def test_foco_vertical_usa_o_inicio_da_interacao_atual(monkeypatch) -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_003",
        description="Mary reage.",
        entries=(VisualEntry("fala", "mary", "Mary", "Ai!"),),
    )
    view = NovelFrameView(page, frame)  # type: ignore[arg-type]
    calls: list[dict[str, object]] = []

    async def immediate_sleep(_delay: float) -> None:
        return None

    async def record_scroll(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr("flet_client.frame_view.asyncio.sleep", immediate_sleep)
    monkeypatch.setattr(view.track, "scroll_to", record_scroll)

    asyncio.run(view._focus_current_after_mount())

    assert calls == [
        {
            "scroll_key": "frame-row-encontro_003",
            "duration": 420,
        }
    ]


def test_fala_balao_recebe_tipografia_de_destaque() -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_003",
        description="Mary reage.",
        entries=(
            VisualEntry(
                "fala",
                "mary_balao",
                "Mary",
                "Ai!!! Que susto!",
                impact_balloon=True,
            ),
        ),
    )
    view = NovelFrameView(page, frame)  # type: ignore[arg-type]

    balloon = _slide_balloon(_interaction_slides(view)[0])
    card = balloon.controls[-1]
    assert isinstance(card, ft.Container)
    column = card.content
    assert isinstance(column, ft.Column)
    copy = column.controls[-1]
    assert isinstance(copy, ft.Text)
    assert copy.size == 23
    assert copy.weight == ft.FontWeight.BOLD


def test_uma_interacao_mantem_quatro_imagens_na_mesma_linha() -> None:
    page = _Page()
    frame = VisualFrame(
        frame_id="encontro_001",
        description="Mary entra.",
        entries=tuple(
            VisualEntry("fala", "mary", "Mary", f"Linha {index}.")
            for index in range(1, 5)
        ),
    )
    view = NovelFrameView(
        page,  # type: ignore[arg-type]
        frame,
        entry_images=tuple(f"https://img/mary{index}.webp" for index in range(1, 5)),
        revealed_entries=4,
    )

    assert len(view.track.controls) == 1
    assert len(_interaction_slides(view)) == 4
    assert [_slide_image(slide).src for slide in _interaction_slides(view)] == [
        f"https://img/mary{index}.webp" for index in range(1, 5)
    ]


def test_tela_preserva_no_maximo_cinco_interacoes_de_quatro_imagens() -> None:
    page = _Page()
    history = ()
    current = None
    for frame_index in range(1, 7):
        entries = tuple(
            VisualEntry("fala", "mary", "Mary", f"F{frame_index} L{entry_index}.")
            for entry_index in range(1, 5)
        )
        current = NovelFrameView(
            page,  # type: ignore[arg-type]
            VisualFrame(
                f"encontro_{frame_index:03d}",
                f"Quadro {frame_index}.",
                entries,
            ),
            entry_images=tuple(
                f"https://img/f{frame_index}-{entry_index}.webp"
                for entry_index in range(1, 5)
            ),
            history=history,
            revealed_entries=4,
        )
        history = current.history_snapshot()

    assert current is not None
    assert len(current.track.controls) == 5
    assert [row.key for row in current.track.controls] == [
        f"frame-row-encontro_{frame_index:03d}" for frame_index in range(2, 7)
    ]
    assert all(len(_interaction_slides(current, index)) == 4 for index in range(5))


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
