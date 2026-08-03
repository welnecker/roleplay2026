from __future__ import annotations

import time

import streamlit as st

from packages.models import InstalledStoryPackage
from persistence.factory import build_google_sheets_repository
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from services.dialogue_presentation import render_dialogue_html, with_optional_thought_guidance
from services.editorial_content import find_editorial_package, load_editorial_package
from services.paid_run_access import get_paid_run_access, terminate_paid_access
from services.pilot_diagnostics import (
    build_turn_diagnostics,
    finalize_model_response,
    log_exception,
    log_turn,
)
from services.pilot_supermarket import (
    PilotScript,
    PilotState,
    clean_model_response,
    decide_turn,
    opening_text,
)
from services.runtime_persistence import (
    RuntimePersistenceContext,
    open_persistent_runtime,
    persist_assistant_message,
    persist_turn,
)
from services.supermarket_script_v2 import (
    automatic_followups_after,
    state_after_automatic_followup,
)
from ui_components import CARD_CSS


MODEL_DEFAULT = "google/gemini-3-flash-preview"
PAYMENT_QUOTA_WINDOW_SECONDS = 65.0


def selected_editorial_package() -> InstalledStoryPackage:
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        raise RuntimeError("Nenhuma história foi selecionada.")
    package = find_editorial_package(package_id)
    if package is None:
        raise RuntimeError(f"O pacote selecionado não possui runtime editorial: {package_id}")
    return package


try:
    PACKAGE = selected_editorial_package()
except Exception as exc:
    st.set_page_config(page_title="História editorial", page_icon="📖", layout="centered")
    st.error(str(exc))
    if st.button("Voltar à biblioteca"):
        st.session_state.page = "library"
        st.session_state.selected_package_id = None
        st.switch_page("app.py")
    st.stop()

PACKAGE_ID = PACKAGE.manifest.package_id
PACKAGE_TITLE = PACKAGE.manifest.card.title
PACKAGE_SUBTITLE = PACKAGE.manifest.card.subtitle
END_CONFIRMATION_KEY = f"confirm_end:{PACKAGE_ID}"

st.set_page_config(page_title=PACKAGE_TITLE, page_icon="📖", layout="centered")
st.markdown(CARD_CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def load_script(package_id: str) -> PilotScript:
    package = find_editorial_package(package_id)
    if package is None:
        raise RuntimeError(f"Pacote editorial não encontrado: {package_id}")
    return load_editorial_package(st.secrets, package)


@st.cache_resource(show_spinner=False)
def runtime_repository():
    return build_google_sheets_repository(st.secrets)


def authenticated_user() -> AuthenticatedUser | None:
    value = st.session_state.get("authenticated_user")
    return value if isinstance(value, AuthenticatedUser) else None


def session_keys(user_id: str) -> tuple[str, str, str, str]:
    prefix = f"editorial:{user_id}:{PACKAGE_ID}"
    return (
        f"{prefix}:context",
        f"{prefix}:story_state",
        f"{prefix}:messages",
        f"{prefix}:editorial_state",
    )


def recover_editorial_state(messages: list[dict[str, object]]) -> PilotState:
    for message in reversed(messages):
        raw = message.get("pilot_state")
        if isinstance(raw, dict):
            return PilotState.from_dict(raw)
    return PilotState()


def ensure_runtime(
    user: AuthenticatedUser,
    *,
    package_version: str,
    restart: bool = False,
) -> tuple[RuntimePersistenceContext, StoryState, list[dict[str, object]], PilotState]:
    context_key, story_key, messages_key, state_key = session_keys(user.user_id)
    if restart:
        for key in (context_key, story_key, messages_key, state_key):
            st.session_state.pop(key, None)

    context = st.session_state.get(context_key)
    story_state = st.session_state.get(story_key)
    messages = st.session_state.get(messages_key)
    editorial_state = st.session_state.get(state_key)
    if (
        isinstance(context, RuntimePersistenceContext)
        and isinstance(story_state, StoryState)
        and isinstance(messages, list)
        and isinstance(editorial_state, PilotState)
    ):
        return context, story_state, messages, editorial_state

    repository = runtime_repository()
    if repository is None:
        raise RuntimeError("Google Sheets não está configurado para esta história.")
    context, story_state, messages = open_persistent_runtime(
        repository,
        user=user,
        package_id=PACKAGE_ID,
        package_version=package_version,
        restart=restart,
        instance_id=str(st.session_state.get("instance_id", "editorial")),
    )
    editorial_state = recover_editorial_state(messages)
    st.session_state[context_key] = context
    st.session_state[story_key] = story_state
    st.session_state[messages_key] = messages
    st.session_state[state_key] = editorial_state
    return context, story_state, messages, editorial_state


def prepare_after_payment(user: AuthenticatedUser) -> bool:
    handoff = st.session_state.get("payment_access_ready")
    if not isinstance(handoff, dict):
        return False
    if str(handoff.get("user_id", "")) != user.user_id:
        return False
    if str(handoff.get("package_id", "")) != PACKAGE_ID:
        return False

    created_at = float(handoff.get("created_at", 0.0) or 0.0)
    remaining = PAYMENT_QUOTA_WINDOW_SECONDS - max(0.0, time.time() - created_at)
    if remaining > 0:
        with st.status("Preparando sua história...", expanded=True) as status:
            status.write("Organizando sua nova execução. Isso pode levar alguns instantes.")
            time.sleep(remaining)
            status.update(label="Abrindo a história...", state="complete", expanded=False)
    st.session_state.pop("payment_access_ready", None)
    return True


def save_session(
    user: AuthenticatedUser,
    context: RuntimePersistenceContext,
    story_state: StoryState,
    messages: list[dict[str, object]],
    editorial_state: PilotState,
) -> None:
    context_key, story_key, messages_key, state_key = session_keys(user.user_id)
    st.session_state[context_key] = context
    st.session_state[story_key] = story_state
    st.session_state[messages_key] = messages
    st.session_state[state_key] = editorial_state


def clear_session(user: AuthenticatedUser) -> None:
    for key in session_keys(user.user_id):
        st.session_state.pop(key, None)
    st.session_state.pop(END_CONFIRMATION_KEY, None)


def return_to_library() -> None:
    st.session_state.pop(END_CONFIRMATION_KEY, None)
    st.session_state.page = "library"
    st.session_state.selected_package_id = None
    st.session_state.checkout_package_id = None
    st.switch_page("app.py")


def end_story_and_return(user: AuthenticatedUser) -> None:
    try:
        terminate_paid_access(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            ending_code="user_abandoned",
        )
    except Exception as exc:
        log_exception("terminate_paid_access", exc, user_id=user.user_id, package_id=PACKAGE_ID)
        st.error(f"Não foi possível encerrar a história: {exc}")
        return
    clear_session(user)
    st.session_state.started_packages.discard(PACKAGE_ID)
    st.session_state.pop("payment_access_ready", None)
    return_to_library()


def render_message(role: str, content: str) -> None:
    st.markdown(render_dialogue_html(role, content), unsafe_allow_html=True)


def advance_story_state(state: StoryState, *, finished: bool = False) -> StoryState:
    updated = state.copy()
    updated.step_index += 1
    updated.consumed_orders.append(updated.step_index)
    updated.finished = finished
    return updated


def bridge_metadata(node_id: str, editorial_state: PilotState) -> dict[str, object]:
    return {
        "pilot": True,
        "pilot_node": node_id,
        "pilot_engagement": "automatic_bridge",
        "pilot_state": editorial_state.to_dict(),
        "pilot_end_event": "",
        "pilot_run_status": "active",
        "pilot_ending_code": "",
        "automatic_bridge": True,
    }


user = authenticated_user()
if user is None:
    st.error("Entre na sua conta antes de abrir a história.")
    if st.button("Voltar ao início"):
        st.switch_page("app.py")
    st.stop()

fresh_start = prepare_after_payment(user)
try:
    script = load_script(PACKAGE_ID)
except Exception as exc:
    log_exception("load_editorial_script", exc, package_id=PACKAGE_ID)
    st.error(f"Não foi possível carregar o roteiro editorial: {exc}")
    st.stop()

try:
    context, story_state, messages, editorial_state = ensure_runtime(
        user,
        restart=fresh_start,
        package_version=str(script.raw.get("script_version", PACKAGE.manifest.version)),
    )
except Exception as exc:
    log_exception("open_runtime", exc, user_id=user.user_id, package_id=PACKAGE_ID)
    st.error(f"Não foi possível abrir a história: {exc}")
    st.stop()

if not editorial_state.finished and not story_state.finished:
    try:
        access = get_paid_run_access(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
        )
    except Exception as exc:
        log_exception("check_paid_access", exc, user_id=user.user_id, package_id=PACKAGE_ID)
        st.error(f"Não foi possível verificar o acesso: {exc}")
        st.stop()
    if not access.allowed:
        return_to_library()

with st.sidebar:
    st.subheader(PACKAGE_TITLE)
    st.caption(PACKAGE_SUBTITLE or "História editorial")
    st.write(f"Interesse: `{editorial_state.interest}`")
    st.write(f"Desejo: `{editorial_state.desire}`")
    st.write(f"Paciência: `{editorial_state.patience}`")
    st.write(f"Etapa: `{editorial_state.node_id}`")
    if st.button("Retornar aos cards", use_container_width=True):
        return_to_library()

    confirming_end = bool(st.session_state.get(END_CONFIRMATION_KEY, False))
    if not editorial_state.finished and not confirming_end:
        if st.button("Encerrar história", use_container_width=True):
            st.session_state[END_CONFIRMATION_KEY] = True
            st.rerun()
    if not editorial_state.finished and confirming_end:
        st.warning("Encerrar irá gerar a necessidade de um novo pagamento. Continuar?")
        confirm_column, cancel_column = st.columns(2)
        with confirm_column:
            if st.button("Sim, encerrar", type="primary", use_container_width=True):
                end_story_and_return(user)
        with cancel_column:
            if st.button("Cancelar", use_container_width=True):
                st.session_state.pop(END_CONFIRMATION_KEY, None)
                st.rerun()

st.title(PACKAGE_TITLE)
st.caption(PACKAGE_SUBTITLE or "História editorial")

if not messages:
    render_message("assistant", opening_text(script))
for message in messages:
    render_message(str(message.get("role", "assistant")), str(message.get("content", "")))

if editorial_state.finished or story_state.finished:
    if editorial_state.run_status == "completed":
        st.success("História concluída.")
    else:
        st.info("A interação foi encerrada.")
    st.caption("A última fala foi registrada. Esta execução não aceita novas mensagens.")
    if st.button("Voltar à biblioteca", type="primary", use_container_width=True):
        return_to_library()
    st.stop()

user_text = st.chat_input("Responda")
if not user_text:
    st.stop()

try:
    turn = decide_turn(script, editorial_state, user_text)
except Exception as exc:
    log_exception(
        "decide_turn",
        exc,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        node_id=editorial_state.node_id,
        pending_beat_id=editorial_state.pending_next_beat_id,
        user_text=user_text,
    )
    st.error("Não foi possível decidir o próximo movimento da história.")
    st.stop()

api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()
system_prompt = with_optional_thought_guidance(turn.system_prompt)
raw_model_response = ""
cleaned_response = turn.visible_fallback
generation_error = ""
force_fixed = turn.state.facts.get("_force_fixed_response") == "true"
if api_key and not force_fixed:
    history = [
        {"role": str(item.get("role", "assistant")), "content": str(item.get("content", ""))}
        for item in messages[-12:]
    ]
    try:
        raw_model_response = generate_response(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            history=history,
            user_text=user_text,
        )
        cleaned_response = clean_model_response(raw_model_response, turn.visible_fallback)
    except OpenRouterError as exc:
        generation_error = str(exc)
        log_exception(
            "openrouter_generation",
            exc,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            node_id=editorial_state.node_id,
            target_id=turn.target_id,
        )

recent_assistant_messages = [
    str(item.get("content", ""))
    for item in messages
    if str(item.get("role", "")) == "assistant"
][-6:]
guarded = finalize_model_response(
    raw_response=raw_model_response,
    cleaned_response=cleaned_response,
    fallback=turn.visible_fallback,
    recent_assistant_messages=recent_assistant_messages,
)
assistant_text = turn.visible_fallback if force_fixed else guarded.response

diagnostics = build_turn_diagnostics(
    user_text=user_text,
    previous_state=editorial_state,
    turn=turn,
    raw_model_response=raw_model_response,
    final_response=assistant_text,
    fallback=turn.visible_fallback,
    generation_error=generation_error,
    guard_reason="fixed_script_bridge" if force_fixed else guarded.guard_reason,
    repeated_recent_anchor=False if force_fixed else guarded.repeated_recent_anchor,
    system_prompt=system_prompt,
)
log_turn(diagnostics)

updated_story_state = advance_story_state(story_state, finished=turn.finished)
metadata: dict[str, object] = {
    "pilot": True,
    "pilot_node": turn.target_id,
    "pilot_engagement": turn.engagement,
    "pilot_state": turn.state.to_dict(),
    "pilot_end_event": "END_RUN" if turn.finished else "",
    "pilot_run_status": turn.run_status,
    "pilot_ending_code": turn.ending_code,
    "pilot_diagnostics": diagnostics,
}
repository = runtime_repository()
if repository is None:
    st.error("Google Sheets ficou indisponível durante a interação.")
    st.stop()

try:
    updated_context = persist_turn(
        repository,
        context=context,
        user=user,
        state=updated_story_state,
        user_text=user_text,
        assistant_text=assistant_text,
        assistant_metadata=metadata,
    )

    messages.append({"role": "user", "content": user_text})
    messages.append({"role": "assistant", "content": assistant_text, **metadata})
    final_editorial_state = turn.state

    is_organic_interstitial = turn.state.facts.get("_organic_interstitial") == "true"
    if not is_organic_interstitial:
        for followup in automatic_followups_after(turn.target_id):
            final_editorial_state = state_after_automatic_followup(final_editorial_state, followup)
            updated_story_state = advance_story_state(updated_story_state)
            followup_metadata = bridge_metadata(str(followup["target_id"]), final_editorial_state)
            updated_context = persist_assistant_message(
                repository,
                context=updated_context,
                user=user,
                state=updated_story_state,
                assistant_text=str(followup["text"]),
                assistant_metadata=followup_metadata,
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": str(followup["text"]),
                    **followup_metadata,
                }
            )
except Exception as exc:
    log_exception(
        "persist_turn_or_bridge",
        exc,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        node_id=editorial_state.node_id,
        target_id=turn.target_id,
        diagnostics=diagnostics,
    )
    st.error(f"Não foi possível registrar a interação: {exc}")
    st.stop()

save_session(user, updated_context, updated_story_state, messages, final_editorial_state)
if generation_error:
    st.toast(f"OpenRouter indisponível; fala segura usada: {generation_error}")
elif not force_fixed and guarded.repeated_recent_anchor:
    st.toast("Uma repetição narrativa foi bloqueada e a fala do beat foi restaurada.")
st.rerun()
