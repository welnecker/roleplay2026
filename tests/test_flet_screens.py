from __future__ import annotations

import base64

import flet as ft

from flet_client.screens import flet_image_source, library_screen, login_screen
from platform_core.models import AccessStatus, ProgressStatus, StoryCard


def _walk(control: ft.Control):
    yield control
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from _walk(content)
    for child in getattr(control, "controls", ()) or ():
        yield from _walk(child)


def _texts(control: ft.Control) -> list[str]:
    return [item.value for item in _walk(control) if isinstance(item, ft.Text)]


def test_login_identifica_previa_sem_autenticacao_real() -> None:
    screen = login_screen(on_preview_login=lambda: None)

    texts = _texts(screen)
    assert "Bem-vindo de volta" in texts
    assert any("PRÉVIA LOCAL" in value for value in texts)
    assert any(isinstance(item, ft.TextField) and item.password for item in _walk(screen))


def test_capa_data_url_e_convertida_em_bytes_para_flet_desktop() -> None:
    payload = b"capa-webp"
    source = "data:image/webp;base64," + base64.b64encode(payload).decode("ascii")

    assert flet_image_source(source) == payload
    assert flet_image_source("https://example.com/capa.webp") == "https://example.com/capa.webp"
    assert flet_image_source("data:image/webp;base64,invalido***") == ""


def test_biblioteca_renderiza_cards_reais_sem_alterar_acesso() -> None:
    story = StoryCard(
        package_id="roleplay2026.exemplo",
        title="História exemplo",
        subtitle="Uma história para testar.",
        description="Descrição",
        genres=("Romance",),
        access_status=AccessStatus.LOCKED,
        progress_status=ProgressStatus.NOT_STARTED,
        price_label="R$ 9,90",
        cover_url="data:image/webp;base64," + base64.b64encode(b"imagem").decode("ascii"),
    )

    screen = library_screen(
        [story],
        display_name="Visitante",
        on_logout=lambda: None,
        on_open_preview=lambda _card: None,
    )

    texts = _texts(screen)
    assert "Aprecie sem moderação" in texts
    assert "História exemplo" in texts
    assert "R$ 9,90" in texts
    assert story.access_status == AccessStatus.LOCKED
    image = next(item for item in _walk(screen) if isinstance(item, ft.Image))
    assert image.src == b"imagem"
