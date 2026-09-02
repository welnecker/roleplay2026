from __future__ import annotations

import flet as ft
import pytest

from flet_client.frame_state import VisualEntry, VisualFrame
from flet_client.frame_view import NovelFrameView


class _Page:
    def __init__(self, *, width: float = 390, height: float = 800) -> None:
        self.width = width
        self.height = height
        self.updates = 0

    def update(self) -> None:
        self.updates += 1


def _stage_column(view: NovelFrameView) -> ft.Column:
    stage = view.stage.content
    assert isinstance(stage, ft.Container)
    assert isinstance(stage.content, ft.Column)
    return stage.content


def _stage_image(view: NovelFrameView) -> ft.Image:
    image_container = _stage_column(view).controls[0]
    assert isinstance(image_container, ft.Container)
    assert isinstance(image_container.content, ft.Image)
    return image_container.content


def _stage_balloon(view: NovelFrameView) -> ft.Stack:
    balloon = _stage_column(view).controls[-1]
    assert isinstance(balloon, ft.Stack)
    return balloon


def test_palco_mostra_um_conteudo_por_vez_e_revela_o_proximo() -> None:
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

    assert _stage_image(view).src == "https://img/mary1.webp"
    thought_balloon = _stage_balloon(view)
    assert len(thought_balloon.controls[:-1]) == 3
    assert all(
        isinstance(tail, ft.Container) and tail.shape == ft.BoxShape.CIRCLE
        for tail in thought_balloon.controls[:-1]
    )

    view._advance()

    assert persisted == [2]
    assert view.controller.revealed_entries == 2
    assert view.stage_cursor.position == 1
    assert _stage_image(view).src == "https://img/mary2.webp"
    speech_tail = _stage_balloon(view).controls[0]
    assert isinstance(speech_tail, ft.Container)
    assert speech_tail.top == 5
    assert isinstance(speech_tail.rotate, ft.Rotate)


def test_palco_responde_a_largura_e_altura_da_janela() -> None:
    page = _Page(width=390, height=800)
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

    assert view.stage_width == pytest.approx(342.0)
    mobile_image = _stage_column(view).controls[0]
    assert isinstance(mobile_image, ft.Container)
    assert mobile_image.height is not None

    view._resize(type("Resize", (), {"width": 1400, "height": 900})())

    assert view.stage_width == pytest.approx(1080.0)
    desktop_image = _stage_column(view).controls[0]
    assert isinstance(desktop_image, ft.Container)
    assert desktop_image.width == pytest.approx(1080.0)
    assert desktop_image.height is not None
    assert desktop_image.height > mobile_image.height


def test_controles_respeitam_a_area_segura_inferior_do_android() -> None:
    view = NovelFrameView(  # type: ignore[arg-type]
        _Page(),
        VisualFrame(
            "encontro_001",
            "Mary entra.",
            (VisualEntry("fala", "mary", "Mary", "Olá."),),
        ),
    )

    layout = view.root.content
    assert isinstance(layout, ft.Column)
    footer = layout.controls[-1]
    assert isinstance(footer, ft.SafeArea)
    assert footer.avoid_intrusions_bottom is True
    assert footer.maintain_bottom_view_padding is True
    assert footer.minimum_padding == ft.Padding.only(bottom=6)


def test_voltar_e_rever_movem_apenas_o_cursor_visual() -> None:
    page = _Page()
    calls: list[int] = []
    frame = VisualFrame(
        frame_id="encontro_003",
        description="Mary reage.",
        entries=tuple(
            VisualEntry("fala", "mary", "Mary", f"Fala {index}.")
            for index in range(1, 4)
        ),
    )
    view = NovelFrameView(
        page,  # type: ignore[arg-type]
        frame,
        entry_images=tuple(f"https://img/mary{index}.webp" for index in range(1, 4)),
        revealed_entries=3,
        on_reveal=lambda count: calls.append(count) is None,
    )

    assert view.stage_cursor.position == 2
    view._review_previous()
    assert view.stage_cursor.position == 1
    assert _stage_image(view).src == "https://img/mary2.webp"
    view._review_next()
    assert view.stage_cursor.position == 2
    assert view.controller.revealed_entries == 3
    assert calls == []


def test_fala_balao_recebe_tipografia_de_destaque() -> None:
    view = NovelFrameView(  # type: ignore[arg-type]
        _Page(),
        VisualFrame(
            "encontro_003",
            "Mary reage.",
            (
                VisualEntry(
                    "fala",
                    "mary_balao",
                    "Mary",
                    "Ai!!! Que susto!",
                    impact_balloon=True,
                ),
            ),
        ),
    )

    card = _stage_balloon(view).controls[-1]
    assert isinstance(card, ft.Container)
    assert isinstance(card.content, ft.Column)
    copy = card.content.controls[-1]
    assert isinstance(copy, ft.Text)
    assert copy.size == 23
    assert copy.weight == ft.FontWeight.BOLD


def test_quatro_entries_permanecem_revisaveis_no_palco_unico() -> None:
    view = NovelFrameView(  # type: ignore[arg-type]
        _Page(),
        VisualFrame(
            "encontro_001",
            "Mary entra.",
            tuple(
                VisualEntry("fala", "mary", "Mary", f"Linha {index}.")
                for index in range(1, 5)
            ),
        ),
        entry_images=tuple(f"https://img/mary{index}.webp" for index in range(1, 5)),
        revealed_entries=4,
    )

    assert len(view._current_row().items) == 4
    assert view.stage_cursor.position == 3
    assert _stage_image(view).src == "https://img/mary4.webp"
    view._review_previous()
    assert _stage_image(view).src == "https://img/mary3.webp"


def test_imagem_da_descricao_e_preservada_como_primeira_posicao_visual() -> None:
    view = NovelFrameView(  # type: ignore[arg-type]
        _Page(),
        VisualFrame(
            "capitulo1_003",
            "Mary aguarda no escuro.",
            (VisualEntry("pensamento", "mary", "Mary", "Alguém está vindo."),),
        ),
        image="https://img/mary11.webp",
        entry_images=("https://img/mary12.webp",),
    )

    assert len(view._current_row().items) == 2
    assert _stage_image(view).src == "https://img/mary12.webp"
    assert isinstance(_stage_balloon(view), ft.Stack)

    view._review_previous()

    assert _stage_image(view).src == "https://img/mary11.webp"
    assert len(_stage_column(view).controls) == 1


def test_imagem_herdada_da_descricao_nao_cria_posicao_duplicada() -> None:
    view = NovelFrameView(  # type: ignore[arg-type]
        _Page(),
        VisualFrame(
            "capitulo1_001",
            "Mary entra.",
            (VisualEntry("pensamento", "mary", "Mary", "Cheguei."),),
        ),
        image="https://img/mary1.webp",
        entry_images=("https://img/mary1.webp",),
    )

    assert len(view._current_row().items) == 1
    assert _stage_image(view).src == "https://img/mary1.webp"
    assert isinstance(_stage_balloon(view), ft.Stack)


def test_snapshot_preserva_cinco_quadros_sem_renderizar_historico_no_palco() -> None:
    page = _Page()
    history = ()
    current = None
    for frame_index in range(1, 7):
        current = NovelFrameView(
            page,  # type: ignore[arg-type]
            VisualFrame(
                f"encontro_{frame_index:03d}",
                f"Quadro {frame_index}.",
                tuple(
                    VisualEntry("fala", "mary", "Mary", f"F{frame_index} L{entry_index}.")
                    for entry_index in range(1, 5)
                ),
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
    assert [row.frame_id for row in history] == [
        f"encontro_{frame_index:03d}" for frame_index in range(2, 7)
    ]
    assert all(len(row.items) == 4 for row in history)
    assert current.stage_cursor.position == 3
    assert _stage_image(current).src == "https://img/f6-4.webp"


def test_revelacao_falha_restaura_o_indice_visual() -> None:
    view = NovelFrameView(  # type: ignore[arg-type]
        _Page(),
        VisualFrame(
            "encontro_001",
            "Mary entra.",
            (
                VisualEntry("pensamento", "mary", "Mary", "Primeiro."),
                VisualEntry("pensamento", "mary", "Mary", "Segundo."),
            ),
        ),
        on_reveal=lambda _count: False,
    )

    view._advance()

    assert view.controller.revealed_entries == 1
    assert view.stage_cursor.position == 0
    assert view.advance_button.disabled is False
