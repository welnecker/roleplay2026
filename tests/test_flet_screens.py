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


def test_login_identifica_api_real_configurada() -> None:
    screen = login_screen(
        on_login=lambda _email, _password: None,
        on_register=lambda _name, _email, _password, _confirmation: None,
        api_url="https://api.example.com",
    )

    texts = _texts(screen)
    assert "Bem-vindo de volta" in texts
    assert "API CONFIGURADA · https://api.example.com" in texts
    assert "Entrar" in [
        item.content
        for item in _walk(screen)
        if isinstance(item, ft.FilledButton)
    ]
    assert any(isinstance(item, ft.TextField) and item.password for item in _walk(screen))


def test_login_bem_sucedido_nao_atualiza_controle_removido_da_pagina() -> None:
    screen = login_screen(
        on_login=lambda _email, _password: None,
        on_register=lambda _name, _email, _password, _confirmation: None,
        api_url="https://api.example.com",
    )
    fields = [item for item in _walk(screen) if isinstance(item, ft.TextField)]
    fields[0].value = "pessoa@example.com"
    fields[1].value = "senha"
    button = next(item for item in _walk(screen) if isinstance(item, ft.FilledButton))
    error = next(
        item
        for item in _walk(screen)
        if isinstance(item, ft.Text) and item.color == "#B42318"
    )

    button.on_click(None)

    assert error.visible is False
    assert not error.value


def test_login_oferece_aba_de_cadastro_e_envia_os_campos() -> None:
    submitted: list[tuple[str, str, str, str]] = []
    screen = login_screen(
        on_login=lambda _email, _password: None,
        on_register=lambda name, email, password, confirmation: (
            submitted.append((name, email, password, confirmation)) or None
        ),
        api_url="https://api.example.com",
    )
    register_tab = next(
        item
        for item in _walk(screen)
        if isinstance(item, ft.Container)
        and isinstance(item.content, ft.Text)
        and item.content.value == "Criar conta"
    )
    register_tab.on_click(None)
    register_panel = next(
        item for item in _walk(screen) if isinstance(item, ft.Column) and item.key == "register-panel"
    )
    login_panel = next(
        item for item in _walk(screen) if isinstance(item, ft.Column) and item.key == "login-panel"
    )
    assert register_panel.visible is True
    assert login_panel.visible is False

    fields = {
        item.label: item
        for item in _walk(register_panel)
        if isinstance(item, ft.TextField)
    }
    fields["Nome de exibição"].value = "Pessoa Nova"
    fields["E-mail"].value = "nova@example.com"
    fields["Senha"].value = "senha-segura"
    fields["Confirmar senha"].value = "senha-segura"
    button = next(
        item
        for item in _walk(register_panel)
        if isinstance(item, ft.FilledButton) and item.content == "Criar conta"
    )
    button.on_click(None)

    assert submitted == [
        ("Pessoa Nova", "nova@example.com", "senha-segura", "senha-segura")
    ]


def test_capa_data_url_e_convertida_em_base64_puro_para_flet_desktop() -> None:
    payload = b"capa-webp"
    encoded = base64.b64encode(payload).decode("ascii")
    source = "data:image/webp;base64," + encoded

    assert flet_image_source(source) == encoded
    assert flet_image_source("https://example.com/capa.webp") == "https://example.com/capa.webp"


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
        cover_url="https://api.example.com/api/v1/catalog/roleplay2026.exemplo/cover",
        profile_name="Personagem Exemplo",
        profile_identity="Quem é a personagem.",
        profile_personality="Como a personagem se comporta.",
        profile_intention="O que pretende com você.",
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
    assert image.src == story.cover_url
    assert image.fit == ft.BoxFit.CONTAIN
    assert (image.left, image.top, image.right, image.bottom) == (0, 0, 0, 0)
    stack = next(item for item in _walk(screen) if isinstance(item, ft.Stack))
    assert stack.height == 280
    assert stack.fit == ft.StackFit.EXPAND
    button = next(item for item in _walk(screen) if isinstance(item, ft.FilledButton))
    assert button.disabled is False
    assert button.content == "Comprar com Pix"

    switcher = next(item for item in _walk(screen) if isinstance(item, ft.AnimatedSwitcher))
    assert switcher.transition == ft.AnimatedSwitcherTransition.ROTATION
    flip_button = next(
        item
        for item in _walk(screen)
        if isinstance(item, ft.TextButton) and item.content == "↻ Conhecer personagem"
    )
    flip_button.on_click(None)

    assert isinstance(switcher.content, ft.Container)
    assert switcher.content.key == "card-back-roleplay2026.exemplo"
    back_texts = _texts(switcher.content)
    assert "Personagem Exemplo" in back_texts
    assert "QUEM É" in back_texts
    assert "Quem é a personagem." in back_texts
    assert "COMO É" in back_texts
    assert "O QUE PRETENDE COM VOCÊ" in back_texts
