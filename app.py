from __future__ import annotations

import streamlit as st

from platform_core.auth import AuthenticatedUser, authenticate_demo
from platform_core.catalog import load_demo_catalog
from platform_core.models import AccessStatus, ProgressStatus, StoryCard
from roleplay.engine import StoryEngine
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from roleplay.prompt_builder import build_system_prompt
from roleplay.validator import enforce_movement
from stories import CASADA_FRUSTRADA
from ui_components import inject_theme, render_story_card


MODEL_DEFAULT = "google/gemini-3-flash-preview"
DEMO_PACKAGE_ID = "roleplay2026.degustacao"

st.set_page_config(
    page_title="Roleplay 2026",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_theme()


def initialize_state() -> None:
    st.session_state.setdefault("authenticated_user", None)
    st.session_state.setdefault("page", "library")
    st.session_state.setdefault("selected_package_id", None)
    st.session_state.setdefault("story_states", {})
    st.session_state.setdefault("story_messages", {})
    st.session_state.setdefault("started_packages", set())
    st.session_state.setdefault("checkout_package_id", None)


def current_user() -> AuthenticatedUser | None:
    value = st.session_state.authenticated_user
    return value if isinstance(value, AuthenticatedUser) else None


def catalog_for_user() -> list[StoryCard]:
    started = st.session_state.started_packages
    result: list[StoryCard] = []
    for story in load_demo_catalog():
        progress = (
            ProgressStatus.IN_PROGRESS
            if story.package_id in started
            else story.progress_status
        )
        result.append(
            StoryCard(
                package_id=story.package_id,
                title=story.title,
                subtitle=story.subtitle,
                description=story.description,
                genres=story.genres,
                access_status=story.access_status,
                progress_status=progress,
                price_label=story.price_label,
                chapter_label=story.chapter_label,
                cover_url=story.cover_url,
                is_tasting=story.is_tasting,
            )
        )
    return result


def open_story(package_id: str, *, restart: bool = False) -> None:
    if restart or package_id not in st.session_state.story_states:
        st.session_state.story_states[package_id] = StoryState()
        st.session_state.story_messages[package_id] = []
    st.session_state.started_packages.add(package_id)
    st.session_state.selected_package_id = package_id
    st.session_state.page = "player"
    st.rerun()


def show_checkout(package_id: str) -> None:
    st.session_state.checkout_package_id = package_id
    st.session_state.page = "checkout"
    st.rerun()


def render_login() -> None:
    left, center, right = st.columns([1, 1.15, 1])
    with center:
        st.markdown("<div class='hero'><h1>Roleplay 2026</h1></div>", unsafe_allow_html=True)
        st.write("Uma biblioteca de histórias interativas independentes.")
        with st.form("login_form"):
            st.subheader("Entrar")
            email = st.text_input("E-mail", placeholder="voce@email.com")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Acessar biblioteca", use_container_width=True, type="primary")
        st.caption("Protótipo: qualquer e-mail válido e senha não vazia permitem o acesso.")
        if submitted:
            user = authenticate_demo(email, password)
            if user is None:
                st.error("Informe um e-mail válido e uma senha.")
            else:
                st.session_state.authenticated_user = user
                st.session_state.page = "library"
                st.rerun()


def render_library(user: AuthenticatedUser) -> None:
    header, actions = st.columns([4, 1])
    with header:
        st.title("Sua biblioteca")
        st.caption(f"Olá, {user.display_name}. Escolha uma história para começar ou continuar.")
    with actions:
        if st.button("Sair", use_container_width=True):
            st.session_state.authenticated_user = None
            st.session_state.page = "library"
            st.rerun()

    stories = catalog_for_user()
    for start in range(0, len(stories), 3):
        columns = st.columns(3)
        for column, story in zip(columns, stories[start : start + 3], strict=False):
            with column:
                render_story_card(
                    story,
                    on_start=lambda package_id: open_story(package_id),
                    on_continue=lambda package_id: open_story(package_id),
                    on_restart=lambda package_id: open_story(package_id, restart=True),
                    on_buy=show_checkout,
                )

    st.divider()
    st.info(
        "Nesta interface inicial, a degustação está liberada. As demais histórias "
        "demonstram o fluxo de compra por Pix, ainda sem criar cobrança real."
    )


def render_checkout() -> None:
    package_id = st.session_state.checkout_package_id
    story = next((item for item in load_demo_catalog() if item.package_id == package_id), None)
    if story is None:
        st.session_state.page = "library"
        st.rerun()

    if st.button("← Voltar à biblioteca"):
        st.session_state.page = "library"
        st.rerun()

    st.title(story.title)
    st.subheader("Pagamento por Pix")
    st.write(story.description)
    st.metric("Valor", story.price_label)
    st.warning(
        "Integração Mercado Pago ainda não ativada. Esta tela já delimita o ponto "
        "onde serão exibidos QR Code, Pix Copia e Cola e atualização do pagamento."
    )
    st.button("Gerar Pix", disabled=True, use_container_width=True, type="primary")


def render_player(package_id: str) -> None:
    if package_id != DEMO_PACKAGE_ID:
        st.warning("O player desta história será ativado quando o conteúdo for cadastrado.")
        if st.button("Voltar à biblioteca"):
            st.session_state.page = "library"
            st.rerun()
        return

    engine = StoryEngine(CASADA_FRUSTRADA)
    state: StoryState = st.session_state.story_states.setdefault(package_id, StoryState())
    messages: list[dict[str, object]] = st.session_state.story_messages.setdefault(package_id, [])

    with st.sidebar:
        st.subheader("História de degustação")
        step = engine.current_step(state)
        if step is None:
            st.write("História concluída")
        else:
            st.write(f"Rota: `{step[0]}`")
            st.write(f"Beat: `{step[1]}`")
        st.write(f"Ordens consumidas: `{state.consumed_orders}`")
        if st.button("Voltar à biblioteca", use_container_width=True):
            st.session_state.page = "library"
            st.rerun()
        if st.button("Reiniciar história", use_container_width=True):
            open_story(package_id, restart=True)

    st.title("Primeiro Encontro")
    st.caption("Degustação do motor narrativo determinístico.")

    for message in messages:
        with st.chat_message(str(message["role"])):
            st.markdown(str(message["content"]))
            if message.get("screenplay_order") is not None:
                st.caption(f"Roteiro: ordem {message['screenplay_order']}")

    if state.finished:
        st.success("História concluída.")
        return

    user_text = st.chat_input("Escreva sua mensagem")
    if not user_text:
        return

    movement = engine.next_movement(state)
    if movement is None:
        st.session_state.story_states[package_id] = state
        st.rerun()

    messages.append({"role": "user", "content": user_text})
    api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
    model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()
    raw_response = movement.content
    generation_error = ""

    if api_key:
        history = [
            {"role": str(item["role"]), "content": str(item["content"])}
            for item in messages[:-1][-12:]
        ]
        try:
            raw_response = generate_response(
                api_key=api_key,
                model=model,
                system_prompt=build_system_prompt(movement=movement),
                history=history,
                user_text=user_text,
            )
        except OpenRouterError as exc:
            generation_error = str(exc)

    final_response, used_fallback = enforce_movement(raw_response, movement)
    updated_state = engine.consume(state, movement)
    st.session_state.story_states[package_id] = updated_state
    messages.append(
        {
            "role": "assistant",
            "content": final_response,
            "screenplay_order": movement.order,
            "screenplay_route": movement.route,
            "screenplay_beat": movement.beat,
            "screenplay_fallback": used_fallback or bool(generation_error),
        }
    )
    st.session_state.story_messages[package_id] = messages
    if generation_error:
        st.toast(f"OpenRouter indisponível; movimento local usado: {generation_error}")
    st.rerun()


initialize_state()
user = current_user()
if user is None:
    render_login()
else:
    page = st.session_state.page
    if page == "checkout":
        render_checkout()
    elif page == "player" and st.session_state.selected_package_id:
        render_player(str(st.session_state.selected_package_id))
    else:
        render_library(user)
