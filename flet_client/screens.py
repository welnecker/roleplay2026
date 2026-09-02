from __future__ import annotations

from collections.abc import Callable, Sequence

import flet as ft

from flet_client.models import AccessStatus, StoryCard


BACKGROUND = "#143936"
SURFACE = "#F9F2F5"
SURFACE_MUTED = "#EEDDE5"
ACCENT = "#D24369"
ACCENT_DARK = "#A52D50"
INK = "#2B1822"
MUTED = "#765E68"


def _update_attached(control: ft.Control) -> None:
    """Atualiza somente controles ainda montados na página Flet."""

    try:
        page = control.page
    except RuntimeError:
        return
    if page is not None:
        page.update()


def flet_image_source(source: str) -> str:
    """Remove o cabeçalho data URL e entrega Base64 puro ao Flet desktop."""

    value = str(source or "").strip()
    if not value.startswith("data:image/") or ";base64," not in value:
        return value
    _header, encoded = value.split(",", maxsplit=1)
    return encoded.strip()


def _logo() -> ft.Column:
    return ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=2,
        controls=[
            ft.Text("ENTRE", size=13, weight=ft.FontWeight.BOLD, color="#FFFFFFAA"),
            ft.Text("CENAS", size=34, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
            ft.Container(width=52, height=3, bgcolor=ACCENT, border_radius=2),
        ],
    )


def login_screen(
    *,
    on_login: Callable[[str, str], str | None],
    on_register: Callable[[str, str, str, str], str | None],
    api_url: str,
) -> ft.Control:
    login_email = ft.TextField(
        label="E-mail",
        hint_text="voce@email.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        border_radius=14,
        autofocus=True,
    )
    login_password = ft.TextField(
        label="Senha",
        password=True,
        can_reveal_password=True,
        border_radius=14,
    )
    login_error = ft.Text(size=12, color="#B42318", visible=False)
    register_name = ft.TextField(label="Nome de exibição", border_radius=14)
    register_email = ft.TextField(
        label="E-mail",
        hint_text="voce@email.com",
        keyboard_type=ft.KeyboardType.EMAIL,
        border_radius=14,
    )
    register_password = ft.TextField(
        label="Senha",
        password=True,
        can_reveal_password=True,
        border_radius=14,
    )
    register_confirmation = ft.TextField(
        label="Confirmar senha",
        password=True,
        can_reveal_password=True,
        border_radius=14,
    )
    register_error = ft.Text(size=12, color="#B42318", visible=False)

    def set_error(control: ft.Text, message: str | None) -> None:
        control.value = str(message or "")
        control.visible = bool(message)
        _update_attached(control)

    def submit(_event: object = None) -> None:
        clean_email = str(login_email.value or "").strip()
        clean_password = str(login_password.value or "")
        if not clean_email or not clean_password:
            message = "Informe seu e-mail e sua senha."
        else:
            message = on_login(clean_email, clean_password)
        if message is None:
            return
        set_error(login_error, message)

    def submit_register(_event: object = None) -> None:
        name = str(register_name.value or "").strip()
        clean_email = str(register_email.value or "").strip()
        password = str(register_password.value or "")
        confirmation = str(register_confirmation.value or "")
        if not name or not clean_email or not password or not confirmation:
            message = "Preencha nome, e-mail, senha e confirmação."
        elif password != confirmation:
            message = "As senhas não coincidem."
        else:
            message = on_register(name, clean_email, password, confirmation)
        if message is None:
            return
        set_error(register_error, message)

    login_panel = ft.Column(
        key="login-panel",
        spacing=17,
        controls=[
            ft.Text("Bem-vindo de volta", size=25, weight=ft.FontWeight.BOLD, color=INK),
            ft.Text("Entre para continuar suas histórias.", size=14, color=MUTED),
            login_email,
            login_password,
            login_error,
            ft.FilledButton(
                "Entrar",
                height=52,
                bgcolor=ACCENT,
                color="#FFFFFF",
                on_click=submit,
            ),
            ft.TextButton("Esqueci minha senha", disabled=True),
        ],
    )
    register_panel = ft.Column(
        key="register-panel",
        spacing=15,
        visible=False,
        controls=[
            ft.Text("Crie sua conta", size=25, weight=ft.FontWeight.BOLD, color=INK),
            ft.Text("Seu progresso ficará associado ao seu cadastro.", size=14, color=MUTED),
            register_name,
            register_email,
            register_password,
            ft.Text("Use ao menos 8 caracteres.", size=11, color=MUTED),
            register_confirmation,
            register_error,
            ft.FilledButton(
                "Criar conta",
                height=52,
                bgcolor=ACCENT,
                color="#FFFFFF",
                on_click=submit_register,
            ),
        ],
    )
    login_tab_text = ft.Text("Entrar", weight=ft.FontWeight.BOLD, color="#FFFFFF")
    register_tab_text = ft.Text("Criar conta", weight=ft.FontWeight.BOLD, color=ACCENT_DARK)
    login_tab = ft.Container(
        expand=True,
        padding=12,
        border_radius=12,
        bgcolor=ACCENT,
        alignment=ft.Alignment.CENTER,
        content=login_tab_text,
    )
    register_tab = ft.Container(
        expand=True,
        padding=12,
        border_radius=12,
        bgcolor=SURFACE_MUTED,
        alignment=ft.Alignment.CENTER,
        content=register_tab_text,
    )

    def select_tab(registering: bool) -> None:
        login_panel.visible = not registering
        register_panel.visible = registering
        login_tab.bgcolor = SURFACE_MUTED if registering else ACCENT
        register_tab.bgcolor = ACCENT if registering else SURFACE_MUTED
        login_tab_text.color = ACCENT_DARK if registering else "#FFFFFF"
        register_tab_text.color = "#FFFFFF" if registering else ACCENT_DARK
        _update_attached(register_panel if registering else login_panel)

    login_tab.on_click = lambda _event: select_tab(False)
    register_tab.on_click = lambda _event: select_tab(True)

    return ft.Container(
        expand=True,
        bgcolor=BACKGROUND,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=22, vertical=30),
        content=ft.Column(
            width=430,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=22,
            controls=[
                _logo(),
                ft.Container(
                    bgcolor=SURFACE,
                    border_radius=26,
                    padding=ft.Padding.symmetric(horizontal=28, vertical=26),
                    shadow=ft.BoxShadow(
                        blur_radius=28,
                        color="#50000000",
                        offset=ft.Offset(0, 10),
                    ),
                    content=ft.Column(
                        spacing=17,
                        controls=[
                            ft.Row([login_tab, register_tab], spacing=8),
                            login_panel,
                            register_panel,
                        ],
                    ),
                ),
                ft.Container(
                    border=ft.Border.all(1, "#FFFFFF33"),
                    border_radius=12,
                    padding=12,
                    content=ft.Text(
                        f"API CONFIGURADA · {api_url}" if api_url else "API NÃO CONFIGURADA",
                        size=11,
                        text_align=ft.TextAlign.CENTER,
                        color="#FFFFFFBB",
                    ),
                ),
            ],
        ),
    )


def _status(card: StoryCard) -> tuple[str, str]:
    if card.access_status == AccessStatus.FREE:
        return "DEGUSTAÇÃO", "#3D8068"
    if card.access_status == AccessStatus.OWNED:
        return "LIBERADO", "#3D8068"
    return card.price_label or "BLOQUEADO", ACCENT_DARK


def _story_card(card: StoryCard, *, on_open_preview: Callable[[StoryCard], None]) -> ft.Control:
    status_label, status_color = _status(card)
    cover: ft.Control
    if card.cover_url:
        cover = ft.Image(
            src=flet_image_source(card.cover_url),
            fit=ft.BoxFit.CONTAIN,
            left=0,
            top=0,
            right=0,
            bottom=0,
        )
    else:
        cover = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            bgcolor=SURFACE_MUTED,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.IMAGE_OUTLINED, size=46, color=MUTED),
        )

    profile_name = card.profile_name or card.title
    profile_identity = card.profile_identity or card.description
    profile_personality = card.profile_personality or (
        "Uma presença que revela novas camadas ao longo da história."
    )
    profile_intention = card.profile_intention or (
        "Construir uma relação própria com você sem antecipar a trama."
    )

    def profile_section(label: str, value: str) -> ft.Control:
        return ft.Column(
            spacing=4,
            controls=[
                ft.Text(label.upper(), size=10, weight=ft.FontWeight.BOLD, color="#DDB9F7"),
                ft.Text(value, size=14, color="#F5EAF1", selectable=True),
            ],
        )

    def flip(show_back: bool) -> None:
        switcher.content = back if show_back else front
        _update_attached(switcher)

    front = ft.Container(
        key=f"card-front-{card.package_id}",
        height=460,
        bgcolor=SURFACE,
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Stack(
                    height=280,
                    fit=ft.StackFit.EXPAND,
                    controls=[
                        cover,
                        ft.Container(
                            top=14,
                            right=14,
                            bgcolor=status_color,
                            border_radius=20,
                            padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                            content=ft.Text(
                                status_label,
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color="#FFFFFF",
                            ),
                        ),
                    ],
                ),
                ft.Container(
                    padding=20,
                    content=ft.Column(
                        spacing=9,
                        controls=[
                            ft.Text(card.title, size=23, weight=ft.FontWeight.BOLD, color=INK),
                            ft.Text(card.subtitle, size=14, color=MUTED, max_lines=2),
                            ft.Row(
                                spacing=7,
                                controls=[
                                    ft.Container(
                                        bgcolor=SURFACE_MUTED,
                                        border_radius=12,
                                        padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                                        content=ft.Text(genre, size=10, color=INK),
                                    )
                                    for genre in card.genres[:2]
                                ],
                            ),
                            ft.TextButton(
                                "↻ Conhecer personagem",
                                icon=ft.Icons.SWAP_HORIZ,
                                on_click=lambda _event: flip(True),
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )
    back = ft.Container(
        key=f"card-back-{card.package_id}",
        height=460,
        bgcolor=INK,
        padding=22,
        content=ft.Column(
            spacing=15,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text(profile_name, size=25, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                profile_section("Quem é", profile_identity),
                profile_section("Como é", profile_personality),
                profile_section("O que pretende com você", profile_intention),
                ft.TextButton(
                    "↻ Voltar para a capa",
                    icon=ft.Icons.SWAP_HORIZ,
                    style=ft.ButtonStyle(color="#FFFFFF"),
                    on_click=lambda _event: flip(False),
                ),
            ],
        ),
    )
    switcher = ft.AnimatedSwitcher(
        content=front,
        duration=420,
        reverse_duration=420,
        transition=ft.AnimatedSwitcherTransition.ROTATION,
        switch_in_curve=ft.AnimationCurve.EASE_OUT_CUBIC,
        switch_out_curve=ft.AnimationCurve.EASE_IN_CUBIC,
    )

    return ft.Container(
        col={"xs": 12, "sm": 6, "lg": 4, "xl": 3},
        bgcolor=SURFACE,
        border_radius=22,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        shadow=ft.BoxShadow(blur_radius=18, color="#35000000", offset=ft.Offset(0, 7)),
        content=ft.Column(
            spacing=0,
            controls=[
                switcher,
                ft.Container(
                    padding=ft.Padding.only(left=20, right=20, bottom=20),
                    content=ft.FilledButton(
                        "Abrir história"
                        if card.access_status != AccessStatus.LOCKED
                        else "Comprar com Pix",
                        bgcolor=ACCENT,
                        color="#FFFFFF",
                        height=45,
                        on_click=lambda _event, selected=card: on_open_preview(selected),
                    ),
                ),
            ],
        ),
    )


def payment_screen(
    card: StoryCard,
    *,
    master_test_available: bool,
    payment_order_id: str = "",
    qr_code: str = "",
    qr_code_base64: str = "",
    payment_status: str = "not_started",
    on_back: Callable[[], None],
    on_create_pix: Callable[[], None],
    on_master_test: Callable[[], None],
    on_refresh: Callable[[], None],
) -> ft.Control:
    details: list[ft.Control] = []
    if qr_code_base64:
        details.append(
            ft.Image(src=qr_code_base64, width=260, height=260, fit=ft.BoxFit.CONTAIN)
        )
    if qr_code:
        details.extend(
            [
                ft.Text("Pix Copia e Cola", size=15, weight=ft.FontWeight.BOLD, color=INK),
                ft.TextField(value=qr_code, multiline=True, read_only=True, min_lines=3),
            ]
        )
    if payment_order_id:
        details.append(
            ft.FilledButton(
                "Já paguei — verificar agora",
                bgcolor=ACCENT,
                color="#FFFFFF",
                on_click=lambda _event: on_refresh(),
            )
        )
    else:
        details.append(
            ft.FilledButton(
                "Gerar Pix",
                bgcolor=ACCENT,
                color="#FFFFFF",
                on_click=lambda _event: on_create_pix(),
            )
        )
    if master_test_available:
        details.extend(
            [
                ft.Divider(),
                ft.Text(
                    "Ambiente interno autorizado para esta conta.",
                    size=12,
                    color=MUTED,
                ),
                ft.OutlinedButton(
                    "Liberar pagamento de teste",
                    on_click=lambda _event: on_master_test(),
                ),
            ]
        )

    return ft.Container(
        expand=True,
        bgcolor=BACKGROUND,
        padding=ft.Padding.symmetric(horizontal=22, vertical=24),
        content=ft.Column(
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=560,
                    bgcolor=SURFACE,
                    border_radius=22,
                    padding=24,
                    content=ft.Column(
                        spacing=14,
                        controls=[
                            ft.TextButton("← Voltar aos cards", on_click=lambda _event: on_back()),
                            ft.Text("Pagamento por Pix", size=28, weight=ft.FontWeight.BOLD, color=INK),
                            ft.Text(card.title, size=21, weight=ft.FontWeight.BOLD, color=INK),
                            ft.Text(card.description or card.subtitle, color=MUTED),
                            ft.Text(card.price_label, size=24, weight=ft.FontWeight.BOLD, color=ACCENT_DARK),
                            ft.Text(f"Status: {payment_status}", size=12, color=MUTED),
                            *details,
                        ],
                    ),
                )
            ],
        ),
    )


def library_screen(
    cards: Sequence[StoryCard],
    *,
    display_name: str,
    on_logout: Callable[[], None],
    on_open_preview: Callable[[StoryCard], None],
) -> ft.Control:
    return ft.Container(
        expand=True,
        bgcolor=BACKGROUND,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=22, vertical=17),
                    bgcolor="#102E2C",
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("ENTRE CENAS", size=19, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Text(f"Olá, {display_name}", size=13, color="#FFFFFFCC"),
                                    ft.IconButton(
                                        icon=ft.Icons.LOGOUT,
                                        icon_color="#FFFFFF",
                                        tooltip="Sair da prévia",
                                        on_click=lambda _event: on_logout(),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
                ft.Container(
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=22, vertical=24),
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        spacing=20,
                        controls=[
                            ft.Column(
                                spacing=5,
                                controls=[
                                    ft.Text("Aprecie sem moderação", size=30, weight=ft.FontWeight.BOLD, color="#FFFFFF"),
                                    ft.Text(
                                        "Escolha uma história e mergulhe na experiência.",
                                        size=14,
                                        color="#FFFFFFBB",
                                    ),
                                ],
                            ),
                            ft.ResponsiveRow(
                                spacing=18,
                                run_spacing=18,
                                controls=[
                                    _story_card(card, on_open_preview=on_open_preview)
                                    for card in cards
                                ],
                            ),
                            ft.Container(height=12),
                        ],
                    ),
                ),
            ],
        ),
    )


__all__ = [
    "BACKGROUND",
    "flet_image_source",
    "library_screen",
    "login_screen",
    "payment_screen",
]
