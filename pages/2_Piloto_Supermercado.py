from __future__ import annotations

import time
from pathlib import Path

import streamlit as st

from persistence.factory import build_google_sheets_repository
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from services.paid_run_access import finish_active_run, get_paid_run_access
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
    persist_turn,
)
from services.v2_run_starter import start_v2_run_on_first_message


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ID = "roleplay2026.casada_frustrada"
SCRIPT_PATH = ROOT / "installed_stories" / "casada_frustrada" / "dialogue_pilot.yaml"
MODEL_DEFAULT = "google/gemini-3-flash-preview"
PAYMENT_QUOTA_WINDOW_SECONDS = 65.0

st.set_page_config(page_title="Casada frustrada — piloto", page_icon="🛒", layout="centered")


@st.cache_resource(show_spinner=False)
def load_script() -> PilotScript:
    return PilotScript.load(SCRIPT_PATH)


@st.cache_resource(show_spinner=False)
def runtime_repository():
    return build_google_sheets_repository(st.secrets)


def authenticated_user() -> AuthenticatedUser | None:
    value = st.session_state.get("authenticated_user")
    return value if isinstance(value, AuthenticatedUser) else None


def session_keys(user_id: str) -> tuple[str, str, str, str]:
    prefix = f"pilot:{user_id}:{PACKAGE_ID}"
    return (
        f"{prefix}:context",
        f"{prefix}:story_state",
        f"{prefix}:messages",
        f"{prefix}:pilot_state",
    )


def recover_pilot_state(messages: list[dict[str, object]]) -> PilotState:
    for message in reversed(messages):
        raw = message.get("pilot_state")
        if isinstance(raw, dict):
            return PilotState.from_dict(raw)
    return PilotState()


def ensure_runtime(
    user: AuthenticatedUser,
    *,
    restart: bool = False,
) -> tuple[
    RuntimePersistenceContext,
    StoryState,
    list[dict[str, object]],
    PilotState,
]:
    context_key, story_key, messages_key, pilot_key = session_keys(user.user_id)
    context = st.session_state.get(context_key)
    story_state = st.session_state.get(story_key)
    messages = st.session_state.get(messages_key)
    pilot_state = st.session_state.get(pilot_key)
    if not restart and (
        isinstance(context, RuntimePersistenceContext)
        and isinstance(story_state, StoryState)
        and isinstance(messages, list)
        and isinstance(pilot_state, PilotState)
    ):
        return context, story_state, messages, pilot_state

    if restart:
        clear_session(user)

    repository = runtime_repository()
    if repository is None:
        raise RuntimeError("Google Sheets não está configurado para o piloto.")
    context, story_state, messages = open_persistent_runtime(
        repository,
        user=user,
        package_id=PACKAGE_ID,
        package_version="0.1.0-pilot",
        restart=restart,
        instance_id=str(st.session_state.get("instance_id", "pilot")),
    )
    pilot_state = recover_pilot_state(messages)
    st.session_state[context_key] = context
    st.session_state[story_key] = story_state
    st.session_state[messages_key] = messages
    st.session_state[pilot_key] = pilot_state
    return context, story_state, messages, pilot_state


def prepare_after_payment(user: AuthenticatedUser) -> bool:
    """Aguarda a transição paga e informa se deve abrir uma execução nova."""

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
        with st.status("Preparando sua história...", expanded=True) as processing_status:
            processing_status.write("Organizando sua nova execução. Isso pode levar alguns instantes.")
            time.sleep(remaining)
            processing_status.update(
                label="Abrindo a história...",
                state="complete",
                expanded=False,
            )

    st.session_state.pop("payment_access_ready", None)
    return True


def save_session(
    user: AuthenticatedUser,
    context: RuntimePersistenceContext,
    story_state: StoryState,
    messages: list[dict[str, object]],
    pilot_state: PilotState,
) -> None:
    context_key, story_key, messages_key, pilot_key = session_keys(user.user_id)
    st.session_state[context_key] = context
    st.session_state[story_key] = story_state
    st.session_state[messages_key] = messages
    st.session_state[pilot_key] = pilot_state


def clear_session(user: AuthenticatedUser) -> None:
    for key in session_keys(user.user_id):
        st.session_state.pop(key, None)


def return_to_library() -> None:
    """Retorna aos cards sem encerrar nem apagar a execução atual."""

    st.session_state.page = "library"
    st.session_state.selected_package_id = None
    st.session_state.checkout_package_id = None
    st.switch_page("app.py")


def end_story_and_return(user: AuthenticatedUser) -> None:
    """Encerra a execução e remove a continuidade antes de voltar aos cards."""

    try:
        ended = finish_active_run(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            status="terminated",
            ending_code="user_abandoned",
        )
        if ended is None:
            started = start_v2_run_on_first_message(
                secrets=st.secrets,
                user_id=user.user_id,
                package_id=PACKAGE_ID,
                installed_stories_root=ROOT / "installed_stories",
            )
            if started is not None:
                finish_active_run(
                    secrets=st.secrets,
                    user_id=user.user_id,
                    package_id=PACKAGE_ID,
                    status="terminated",
                    ending_code="user_abandoned_before_first_turn",
                )
    except Exception as exc:
        st.error(f"Não foi possível encerrar a história: {exc}")
        return

    clear_session(user)
    st.session_state.started_packages.discard(PACKAGE_ID)
    st.session_state.pop("payment_access_ready", None)
    st.session_state.page = "library"
    st.session_state.selected_package_id = None
    st.session_state.checkout_package_id = None
    st.switch_page("app.py")


user = authenticated_user()
if user is None:
    st.error("Entre na sua conta antes de abrir a história.")
    if st.button("Voltar ao início"):
        st.switch_page("app.py")
    st.stop()

fresh_start = prepare_after_payment(user)
script = load_script()
try:
    context, story_state, messages, pilot_state = ensure_runtime(user, restart=fresh_start)
except Exception as exc:
    st.error(f"Não foi possível abrir o piloto: {exc}")
    st.stop()

# A run finalizada precisa continuar aberta para exibir a última fala e o botão.
# Só verificamos novo direito de acesso enquanto a execução ainda está ativa.
if not pilot_state.finished and not story_state.finished:
    try:
        access = get_paid_run_access(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
        )
    except Exception as exc:
        st.error(f"Não foi possível verificar o acesso: {exc}")
        st.stop()

    if not access.allowed:
        return_to_library()

with st.sidebar:
    st.subheader("Casada frustrada")
    st.caption("Piloto descartável · supermercado")
    st.write(f"Interesse: `{pilot_state.interest}`")
    st.write(f"Desejo: `{pilot_state.desire}`")
    st.write(f"Paciência: `{pilot_state.patience}`")
    st.write(f"Etapa: `{pilot_state.node_id}`")
    if st.button("Retornar aos cards", use_container_width=True):
        return_to_library()
    if not pilot_state.finished and st.button(
        "Encerrar história",
        use_container_width=True,
    ):
        end_story_and_return(user)

st.title("Casada frustrada")
st.caption("Bloco piloto: primeiro contato no supermercado")

if not messages:
    with st.chat_message("assistant"):
        st.markdown(opening_text(script))

for message in messages:
    with st.chat_message(str(message.get("role", "assistant"))):
        st.markdown(str(message.get("content", "")))

if pilot_state.finished or story_state.finished:
    if pilot_state.run_status == "completed":
        st.success("Cena concluída.")
    else:
        st.info("Mary encerrou a interação.")
    st.caption("A última fala foi registrada. Esta execução não aceita novas mensagens.")
    if st.button("Retornar aos cards", type="primary", use_container_width=True):
        clear_session(user)
        st.session_state.started_packages.discard(PACKAGE_ID)
        return_to_library()
    st.stop()

user_text = st.chat_input("Responda a Mary")
if not user_text:
    st.stop()

turn = decide_turn(script, pilot_state, user_text)
api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()
assistant_text = turn.visible_fallback
generation_error = ""
if api_key:
    history = [
        {"role": str(item.get("role", "assistant")), "content": str(item.get("content", ""))}
        for item in messages[-12:]
    ]
    try:
        generated = generate_response(
            api_key=api_key,
            model=model,
            system_prompt=turn.system_prompt,
            history=history,
            user_text=user_text,
        )
        assistant_text = clean_model_response(generated, turn.visible_fallback)
    except OpenRouterError as exc:
        generation_error = str(exc)

updated_story_state = story_state.copy()
updated_story_state.step_index += 1
updated_story_state.consumed_orders.append(updated_story_state.step_index)
updated_story_state.finished = turn.finished
sequence_start = len(messages) + 1
metadata: dict[str, object] = {
    "pilot": True,
    "pilot_node": turn.target_id,
    "pilot_engagement": turn.engagement,
    "pilot_state": turn.state.to_dict(),
    "pilot_end_event": "END_RUN" if turn.finished else "",
    "pilot_run_status": turn.run_status,
    "pilot_ending_code": turn.ending_code,
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
        sequence_start=sequence_start,
    )
except Exception as exc:
    st.error(f"Não foi possível registrar a interação: {exc}")
    st.stop()

messages.append({"role": "user", "content": user_text})
messages.append({"role": "assistant", "content": assistant_text, **metadata})
save_session(user, updated_context, updated_story_state, messages, turn.state)
if generation_error:
    st.toast(f"OpenRouter indisponível; fala segura usada: {generation_error}")
st.rerun()
