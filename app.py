from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import streamlit as st

from packages.engine_adapter import StoryEngineAdapterError, adapt_story_definition
from packages.loader import StoryPackageError, discover_packages
from packages.models import InstalledStoryPackage
from packages.story_content import StoryContentError, load_story_content
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.factory import build_google_sheets_repository
from persistence.google_sheets import GoogleSheetsRuntimeRepository
from persistence.models import ConcurrentSaveUpdateError
from platform_core.auth import AuthenticatedUser, authenticate_demo
from platform_core.catalog import load_demo_catalog
from platform_core.models import AccessStatus, ProgressStatus, StoryCard
from roleplay.engine import StoryEngine
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from roleplay.prompt_builder import build_system_prompt
from roleplay.validator import enforce_movement
from services.runtime_persistence import (
    RuntimePersistenceContext,
    open_persistent_runtime,
    persist_turn,
)
from ui_components import inject_theme, render_story_card


MODEL_DEFAULT = "google/gemini-3-flash-preview"
INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent / "installed_stories"

st.set_page_config(
    page_title="Roleplay 2026",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)
inject_theme()


@st.cache_resource(show_spinner=False)
def runtime_repository() -> tuple[GoogleSheetsRuntimeRepository | None, str]:
    try:
        repository = build_google_sheets_repository(st.secrets)
        return repository, ""
    except Exception as exc:
        return None, str(exc)


@st.cache_resource(show_spinner=False)
def account_repository() -> tuple[GoogleSheetsAccountRepository | None, str]:
    runtime, error = runtime_repository()
    if runtime is None:
        return None, error
    try:
        repository = GoogleSheetsAccountRepository(runtime.spreadsheet)
        repository.ensure_schema()
        return repository, ""
    except Exception as exc:
        return None, str(exc)


def initialize_state() -> None:
    st.session_state.setdefault("authenticated_user", None)
    st.session_state.setdefault("page", "library")
    st.session_state.setdefault("selected_package_id", None)
    st.session_state.setdefault("story_states", {})
    st.session_state.setdefault("story_messages", {})
    st.session_state.setdefault("started_packages", set())
    st.session_state.setdefault("checkout_package_id", None)
    st.session_state.setdefault("runtime_contexts", {})
    st.session_state.setdefault("restart_requests", set())
    st.session_state.setdefault("instance_id", f"streamlit_{uuid4().hex}")


def current_user() -> AuthenticatedUser | None:
    value = st.session_state.authenticated_user
    return value if isinstance(value, AuthenticatedUser) else None


def installed_packages() -> tuple[dict[str, InstalledStoryPackage], list[str]]:
    packages, errors = discover_packages(INSTALLED_STORIES_ROOT)
    return {package.manifest.package_id: package for package in packages}, errors


def user_has_access(user: AuthenticatedUser, package_id: str, access: str) -> bool:
    if access == "free":
        return True
    repository, _error = account_repository()
    if repository is None:
        return False
    return repository.has_entitlement(
        user_id=user.user_id,
        package_id=package_id,
        access=access,
    )


def catalog_for_user(user: AuthenticatedUser) -> list[StoryCard]:
    started = st.session_state.started_packages
    result: list[StoryCard] = []
    for story in load_demo_catalog():
        access = "free" if story.access_status == AccessStatus.FREE else "paid"
        entitled = user_has_access(user, story.package_id, access)
        access_status = (
            AccessStatus.FREE
            if access == "free"
            else AccessStatus.OWNED
            if entitled
            else AccessStatus.LOCKED
        )
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
                access_status=access_status,
                progress_status=progress,
                price_label=story.price_label,
                chapter_label=story.chapter_label,
                cover_url=story.cover_url,
                is_tasting=story.is_tasting,
            )
        )
    return result


def open_story(package_id: str, *, restart: bool = False) -> None:
    if restart:
        st.session_state.restart_requests.add(package_id)
        st.session_state.story_states.pop(package_id, None)
        st.session_state.story_messages.pop(package_id, None)
        st.session_state.runtime_contexts.pop(package_id, None)
    st.session_state.started_packages.add(package_id)
    st.session_state.selected_package_id = package_id
    st.session_state.page = "player"
    st.rerun()


def show_checkout(package_id: str) -> None:
    st.session_state.checkout_package_id = package_id
    st.session_state.page = "checkout"
    st.rerun()


def _to_authenticated_user(user: object) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(getattr(user, "user_id")),
        email=str(getattr(user, "email")),
        display_name=str(getattr(user, "display_name")),
    )


def render_login() -> None:
    _left, center, _right = st.columns([1, 1.15, 1])
    with center:
        st.markdown("<div class='hero'><h1>Roleplay 2026</h1></div>", unsafe_allow_html=True)
        st.write("Uma biblioteca de histórias interativas independentes.")

        repository, account_error = account_repository()
        login_tab, register_tab = st.tabs(["Entrar", "Criar conta"])

        with login_tab:
            with st.form("login_form"):
                email = st.text_input("E-mail", placeholder="voce@email.com", key="login_email")
                password = st.text_input("Senha", type="password", key="login_password")
                submitted = st.form_submit_button(
                    "Acessar biblioteca",
                    use_container_width=True,
                    type="primary",
                )
            if submitted:
                if repository is not None:
                    account = repository.authenticate(email=email, password=password)
                    user = _to_authenticated_user(account) if account is not None else None
                else:
                    user = authenticate_demo(email, password)
                if user is None:
                    st.error("E-mail ou senha inválidos.")
                else:
                    st.session_state.authenticated_user = user
                    st.session_state.page = "library"
                    st.rerun()

        with register_tab:
            if repository is None:
                st.info("O cadastro será habilitado quando o Google Sheets estiver configurado.")
            else:
                with st.form("register_form"):
                    display_name = st.text_input("Nome de exibição")
                    email = st.text_input("E-mail", placeholder="voce@email.com", key="register_email")
                    password = st.text_input("Senha", type="password", key="register_password")
                    password_confirmation = st.text_input(
                        "Confirmar senha",
                        type="password",
                    )
                    submitted_register = st.form_submit_button(
                        "Criar conta",
                        use_container_width=True,
                        type="primary",
                    )
                if submitted_register:
                    if password != password_confirmation:
                        st.error("As senhas não coincidem.")
                    else:
                        try:
                            account = repository.register(
                                email=email,
                                password=password,
                                display_name=display_name,
                            )
                        except ValueError as exc:
                            st.error(str(exc))
                        else:
                            st.session_state.authenticated_user = _to_authenticated_user(account)
                            st.session_state.page = "library"
                            st.rerun()

        if account_error:
            st.caption(
                "Google Sheets indisponível. O login demonstrativo permanece ativo nesta execução: "
                f"{account_error}"
            )
        elif repository is None:
            st.caption("Modo local: qualquer e-mail válido e senha não vazia permitem o acesso.")
        else:
            st.caption("Contas e senhas protegidas por Argon2 no Google Sheets.")


def render_library(user: AuthenticatedUser) -> None:
    header, actions = st.columns([4, 1])
    with header:
        st.title("Sua biblioteca")
        st.caption(f"Olá, {user.display_name}. Escolha uma história para começar ou continuar.")
    with actions:
        if st.button("Sair", use_container_width=True):
            st.session_state.authenticated_user = None
            st.session_state.page = "library"
            st.session_state.selected_package_id = None
            st.session_state.runtime_contexts = {}
            st.rerun()

    stories = catalog_for_user(user)
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

    _packages, package_errors = installed_packages()
    if package_errors:
        with st.expander("Pacotes com erro"):
            for error in package_errors:
                st.error(error)

    repository, persistence_error = runtime_repository()
    if persistence_error:
        st.warning(f"Google Sheets indisponível; usando estado local nesta aba: {persistence_error}")
    elif repository is None:
        st.info(
            "Persistência local ativa. Configure GOOGLE_SHEETS_SPREADSHEET_ID e "
            "[gcp_service_account] para habilitar contas e saves compartilhados."
        )
    else:
        st.success("Contas, entitlements e saves compartilhados no Google Sheets estão ativos.")


def render_checkout(user: AuthenticatedUser) -> None:
    package_id = st.session_state.checkout_package_id
    story = next((item for item in load_demo_catalog() if item.package_id == package_id), None)
    if story is None:
        st.session_state.page = "library"
        st.rerun()

    if user_has_access(user, package_id, "paid"):
        st.success("Esta história já está liberada para sua conta.")
        if st.button("Abrir história", type="primary"):
            open_story(package_id)
        return

    if st.button("← Voltar à biblioteca"):
        st.session_state.page = "library"
        st.rerun()

    st.title(story.title)
    st.subheader("Pagamento por Pix")
    st.write(story.description)
    st.metric("Valor", story.price_label)
    st.warning(
        "Integração Mercado Pago ainda não ativada. O entitlement já é exigido pelo app, "
        "mas a cobrança Pix será conectada no próximo marco."
    )
    st.button("Gerar Pix", disabled=True, use_container_width=True, type="primary")


def load_package_engine(package_id: str) -> tuple[InstalledStoryPackage, StoryEngine]:
    package_map, errors = installed_packages()
    if package_id not in package_map:
        detail = "; ".join(errors) if errors else "pacote não instalado"
        raise StoryPackageError(f"Não foi possível abrir {package_id}: {detail}")

    package = package_map[package_id]
    entrypoint = package.root / package.manifest.entrypoint
    loaded = load_story_content(entrypoint)
    engine_story = adapt_story_definition(loaded.definition)
    return package, StoryEngine(engine_story)


def ensure_runtime_loaded(
    *,
    package: InstalledStoryPackage,
    user: AuthenticatedUser,
) -> tuple[StoryState, list[dict[str, object]], RuntimePersistenceContext | None]:
    package_id = package.manifest.package_id
    restart = package_id in st.session_state.restart_requests
    if package_id in st.session_state.story_states and not restart:
        return (
            st.session_state.story_states[package_id],
            st.session_state.story_messages.setdefault(package_id, []),
            st.session_state.runtime_contexts.get(package_id),
        )

    repository, _error = runtime_repository()
    context: RuntimePersistenceContext | None = None
    if repository is not None:
        context, state, messages = open_persistent_runtime(
            repository,
            user=user,
            package_id=package_id,
            package_version=package.manifest.version,
            restart=restart,
            instance_id=st.session_state.instance_id,
        )
        st.session_state.runtime_contexts[package_id] = context
    else:
        state = StoryState()
        messages = []

    st.session_state.story_states[package_id] = state
    st.session_state.story_messages[package_id] = messages
    st.session_state.restart_requests.discard(package_id)
    return state, messages, context


def render_player(package_id: str, user: AuthenticatedUser) -> None:
    story_card = next((item for item in load_demo_catalog() if item.package_id == package_id), None)
    access = "free" if story_card and story_card.access_status == AccessStatus.FREE else "paid"
    if not user_has_access(user, package_id, access):
        st.session_state.checkout_package_id = package_id
        st.session_state.page = "checkout"
        st.rerun()

    try:
        package, engine = load_package_engine(package_id)
        state, messages, context = ensure_runtime_loaded(package=package, user=user)
    except (StoryPackageError, StoryContentError, StoryEngineAdapterError, RuntimeError) as exc:
        st.error(f"A história não pôde ser carregada: {exc}")
        if st.button("Voltar à biblioteca"):
            st.session_state.page = "library"
            st.rerun()
        return

    with st.sidebar:
        st.subheader(package.manifest.card.title)
        step = engine.current_step(state)
        if step is None:
            st.write("História concluída")
        else:
            st.write(f"Rota: `{step[0]}`")
            st.write(f"Beat: `{step[1]}`")
        st.write(f"Ordens consumidas: `{state.consumed_orders}`")
        if context is not None:
            st.caption(f"Save: `{context.save.save_id}` · versão {context.save.state_version}")
        if st.button("Voltar à biblioteca", use_container_width=True):
            st.session_state.page = "library"
            st.rerun()
        if st.button("Reiniciar história", use_container_width=True):
            open_story(package_id, restart=True)

    st.title(engine.story.title)
    st.caption(package.manifest.card.subtitle or "História carregada por pacote declarativo.")

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

    sequence_start = len(messages) + 1
    api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
    model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()
    raw_response = movement.content
    generation_error = ""

    if api_key:
        history = [
            {"role": str(item["role"]), "content": str(item["content"])}
            for item in messages[-12:]
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
    assistant_metadata: dict[str, object] = {
        "screenplay_order": movement.order,
        "screenplay_route": movement.route,
        "screenplay_beat": movement.beat,
        "screenplay_fallback": used_fallback or bool(generation_error),
    }

    repository, _error = runtime_repository()
    if repository is not None and context is not None:
        try:
            updated_context = persist_turn(
                repository,
                context=context,
                user=user,
                state=updated_state,
                user_text=user_text,
                assistant_text=final_response,
                assistant_metadata=assistant_metadata,
                sequence_start=sequence_start,
            )
            st.session_state.runtime_contexts[package_id] = updated_context
        except ConcurrentSaveUpdateError as exc:
            st.error(
                "Este save foi alterado em outra instância. A resposta não foi aplicada "
                f"para evitar sobrescrever o progresso: {exc}"
            )
            st.session_state.story_states.pop(package_id, None)
            st.session_state.story_messages.pop(package_id, None)
            st.session_state.runtime_contexts.pop(package_id, None)
            return
        except Exception as exc:
            st.error(f"Não foi possível persistir este turno: {exc}")
            return

    messages.append({"role": "user", "content": user_text})
    messages.append(
        {
            "role": "assistant",
            "content": final_response,
            **assistant_metadata,
        }
    )
    st.session_state.story_states[package_id] = updated_state
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
        render_checkout(user)
    elif page == "player" and st.session_state.selected_package_id:
        render_player(str(st.session_state.selected_package_id), user)
    else:
        render_library(user)
