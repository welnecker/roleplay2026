from __future__ import annotations

import time

import streamlit as st

from narrative_v2.repository import RuntimeConflictError
from packages.models import InstalledStoryPackage
from persistence.factory import build_google_sheets_repository
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from services.dialogue_presentation import render_dialogue_html
from services.editorial_content import find_editorial_package, load_editorial_package
from services.editorial_diagnostics import log_editorial_exception
from services.editorial_scene_images import render_editorial_scene_image
from services.immersive_onboarding import (
    build_immersive_context,
    clear_immersive_profile,
    persistent_profile_payload,
    profile_key,
    recover_persistent_profile,
    render_immersive_onboarding,
    restore_profile_for_run,
)
from services.novel_frame_runtime_support import first_frame_movement, is_frame_script
from services.novel_runtime_conflict import persisted_movement_at_sequence
from services.novel_v2_adapter import build_novel_prompt, movement_from_script, next_movement_id
from services.paid_run_access import finish_active_run, get_paid_run_access, terminate_paid_access
from services.pwa import install_pwa_metadata
from services.runtime_persistence import (
    RuntimePersistenceContext,
    open_persistent_runtime,
    persist_assistant_message,
    persist_opening_message,
)
from services.story_profile import personalize_editorial_script
from services.visual_novel_history import current_assistant_messages
from ui_components import CARD_CSS


MODEL_DEFAULT = "google/gemini-3-flash-preview"
PAYMENT_QUOTA_WINDOW_SECONDS = 65.0
OPERATIONAL_GENERATION_ERROR = "Não foi possível gerar a próxima cena agora. Tente novamente."


def selected_package() -> InstalledStoryPackage:
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        raise RuntimeError("Nenhuma história foi selecionada.")
    package = find_editorial_package(package_id)
    if package is None:
        raise RuntimeError(f"Pacote narrativo não encontrado: {package_id}")
    return package


try:
    PACKAGE = selected_package()
except Exception as exc:
    st.set_page_config(page_title="Novela", page_icon="📖", layout="centered")
    st.error(str(exc))
    if st.button("Voltar à biblioteca"):
        st.session_state.page = "library"
        st.session_state.selected_package_id = None
        st.switch_page("app.py")
    st.stop()

PACKAGE_ID = PACKAGE.manifest.package_id
PACKAGE_TITLE = PACKAGE.manifest.card.title
PACKAGE_SUBTITLE = PACKAGE.manifest.card.subtitle
CHARACTER_NAME = (
    PACKAGE.manifest.card.character_profile.name
    if PACKAGE.manifest.card.character_profile
    else PACKAGE_TITLE
)
CHARACTER_ID = CHARACTER_NAME.strip().casefold().replace(" ", "_") or "character"
END_CONFIRMATION_KEY = f"novel_v2:end:{PACKAGE_ID}"

st.set_page_config(page_title=PACKAGE_TITLE, page_icon="📖", layout="centered")
install_pwa_metadata()
st.markdown(CARD_CSS, unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def runtime_repository():
    return build_google_sheets_repository(st.secrets)


def authenticated_user() -> AuthenticatedUser | None:
    value = st.session_state.get("authenticated_user")
    return value if isinstance(value, AuthenticatedUser) else None


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
        with st.status("Preparando sua novela...", expanded=True) as status:
            status.write("Organizando sua nova execução.")
            time.sleep(remaining)
            status.update(label="Abrindo a novela...", state="complete", expanded=False)
    st.session_state.pop("payment_access_ready", None)
    return True


def script_key(user_id: str) -> str:
    return f"novel_v2:script:{user_id}:{PACKAGE_ID}"


def load_script(user: AuthenticatedUser, *, refresh: bool = False):
    key = script_key(user.user_id)
    if refresh:
        st.session_state.pop(key, None)
    cached = st.session_state.get(key)
    if cached is not None:
        return cached
    script = load_editorial_package(st.secrets, PACKAGE)
    st.session_state[key] = script
    return script


def runtime_keys(user_id: str) -> tuple[str, str, str]:
    prefix = f"novel_v2:{user_id}:{PACKAGE_ID}"
    return f"{prefix}:context", f"{prefix}:story_state", f"{prefix}:messages"


def ensure_runtime(
    user: AuthenticatedUser,
    *,
    package_version: str,
    restart: bool = False,
) -> tuple[RuntimePersistenceContext, StoryState, list[dict[str, object]]]:
    context_key, state_key, messages_key = runtime_keys(user.user_id)
    if restart:
        for key in (context_key, state_key, messages_key):
            st.session_state.pop(key, None)
    context = st.session_state.get(context_key)
    state = st.session_state.get(state_key)
    messages = st.session_state.get(messages_key)
    if isinstance(context, RuntimePersistenceContext) and isinstance(state, StoryState) and isinstance(messages, list):
        return context, state, messages
    repository = runtime_repository()
    if repository is None:
        raise RuntimeError("Google Sheets não está configurado para esta história.")
    context, state, messages = open_persistent_runtime(
        repository,
        user=user,
        package_id=PACKAGE_ID,
        package_version=package_version,
        restart=restart,
        instance_id=str(st.session_state.get("instance_id", "novel_v2")),
    )
    st.session_state[context_key] = context
    st.session_state[state_key] = state
    st.session_state[messages_key] = messages
    return context, state, messages


def save_runtime(
    user: AuthenticatedUser,
    context: RuntimePersistenceContext,
    state: StoryState,
    messages: list[dict[str, object]],
) -> None:
    context_key, state_key, messages_key = runtime_keys(user.user_id)
    st.session_state[context_key] = context
    st.session_state[state_key] = state
    st.session_state[messages_key] = messages


def clear_runtime(user: AuthenticatedUser) -> None:
    for key in runtime_keys(user.user_id):
        st.session_state.pop(key, None)
    st.session_state.pop(script_key(user.user_id), None)
    st.session_state.pop(END_CONFIRMATION_KEY, None)
    clear_immersive_profile(st.session_state, user_id=user.user_id, package_id=PACKAGE_ID)


def return_to_library() -> None:
    user = authenticated_user()
    if user is not None:
        st.session_state.pop(script_key(user.user_id), None)
        clear_immersive_profile(st.session_state, user_id=user.user_id, package_id=PACKAGE_ID)
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
        log_editorial_exception("novel_v2_terminate", exc, user_id=user.user_id, package_id=PACKAGE_ID)
        st.error(f"Não foi possível encerrar a novela: {exc}")
        return
    clear_runtime(user)
    st.session_state.started_packages.discard(PACKAGE_ID)
    st.session_state.pop("payment_access_ready", None)
    return_to_library()


def render_message(role: str, content: str) -> None:
    st.markdown(
        render_dialogue_html(role, content, character_name=CHARACTER_NAME),
        unsafe_allow_html=True,
    )


def current_movement_id(messages: list[dict[str, object]]) -> str:
    for message in reversed(messages):
        if str(message.get("role", "")) != "assistant":
            continue
        if bool(message.get("scene_opening", False)):
            continue
        node = str(message.get("editorial_node") or message.get("beat_id") or "").strip()
        if node:
            return node
    return ""


def advance_story_state(state: StoryState, *, finished: bool = False) -> StoryState:
    updated = state.copy()
    updated.step_index += 1
    updated.consumed_orders.append(updated.step_index)
    updated.finished = finished
    return updated


def profile_user_name(profile: object) -> str:
    if not isinstance(profile, dict):
        return ""
    return str(
        profile.get("name")
        or profile.get("user_name")
        or profile.get("nome")
        or profile.get("preferred_name")
        or ""
    ).strip()


def generate_movement_text(*, movement, user_name: str, profile: object, messages: list[dict[str, object]]) -> str:
    if not api_key:
        raise RuntimeError(OPERATIONAL_GENERATION_ERROR)
    system_prompt = build_novel_prompt(
        character_name=CHARACTER_NAME,
        user_name=user_name,
        movement=movement,
    )
    private_context = build_immersive_context(profile)
    history = [
        {"role": "assistant", "content": str(item.get("content", ""))}
        for item in messages[-8:]
        if str(item.get("role", "")) == "assistant"
    ]
    return generate_response(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt + private_context,
        history=history,
        user_text="Avance a novela executando somente o movimento atual.",
        debug_logging=not bool(private_context),
    ).strip()


def persist_movement(
    *,
    user: AuthenticatedUser,
    context: RuntimePersistenceContext,
    state: StoryState,
    messages: list[dict[str, object]],
    target_id: str,
    movement,
    assistant_text: str,
    profile: object,
    input_source: str,
) -> tuple[RuntimePersistenceContext, StoryState]:
    updated_state = advance_story_state(state, finished=movement.is_ending)
    metadata: dict[str, object] = {
        "character_id": CHARACTER_ID,
        "editorial_node": target_id,
        "editorial_block": movement.block_id,
        "novel_v2": True,
        "novel_movement": True,
        "novel_frame": is_frame_script(script),
        "input_source": input_source,
    }
    immersive_memory = persistent_profile_payload(profile)
    if immersive_memory and recover_persistent_profile(messages) is None:
        metadata["immersive_profile"] = immersive_memory
    repository = runtime_repository()
    if repository is None:
        raise RuntimeError("Google Sheets ficou indisponível ao registrar a cena.")
    try:
        updated_context = persist_assistant_message(
            repository,
            context=context,
            user=user,
            state=updated_state,
            assistant_text=assistant_text,
            assistant_metadata=metadata,
        )
    except RuntimeConflictError:
        # Outra sessão pode ter persistido exatamente este movimento enquanto
        # esta ainda gerava o texto. A resposta salva é a autoridade. Só adota
        # o conflito quando sequência e movimento coincidem; colisões reais
        # entre movimentos diferentes continuam sendo rejeitadas.
        recovered_context, recovered_state, recovered_messages = open_persistent_runtime(
            repository,
            user=user,
            package_id=PACKAGE_ID,
            package_version=context.package_version,
            restart=False,
            instance_id=context.instance_id,
        )
        persisted = persisted_movement_at_sequence(
            recovered_messages,
            sequence=context.next_sequence,
            target_id=target_id,
        )
        if persisted is None:
            raise
        messages[:] = recovered_messages
        return recovered_context, recovered_state
    messages.append({"role": "assistant", "content": assistant_text, **metadata})
    if movement.is_ending:
        finish_active_run(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            status="completed",
            ending_code="normal_completion",
        )
    return updated_context, updated_state


user = authenticated_user()
if user is None:
    st.error("Entre na sua conta antes de abrir a história.")
    if st.button("Voltar ao início"):
        st.switch_page("app.py")
    st.stop()

fresh_start = prepare_after_payment(user)
api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()
try:
    script = load_script(user, refresh=fresh_start)
except Exception as exc:
    log_editorial_exception("novel_v2_load_script", exc, package_id=PACKAGE_ID)
    st.error(f"Não foi possível carregar o roteiro: {exc}")
    st.stop()

try:
    context, story_state, messages = ensure_runtime(
        user,
        restart=fresh_start,
        package_version=str(script.raw.get("script_version", PACKAGE.manifest.version)),
    )
except Exception as exc:
    log_editorial_exception("novel_v2_open_runtime", exc, user_id=user.user_id, package_id=PACKAGE_ID)
    st.error(f"Não foi possível abrir a novela: {exc}")
    st.stop()

restore_profile_for_run(st.session_state, user_id=user.user_id, package_id=PACKAGE_ID, messages=messages)
if not render_immersive_onboarding(
    user_id=user.user_id,
    package_id=PACKAGE_ID,
    title=PACKAGE_TITLE,
    character_name=CHARACTER_NAME,
    api_key=api_key,
    model=model,
):
    st.stop()
immersive_profile = st.session_state.get(profile_key(user.user_id, PACKAGE_ID))
if isinstance(immersive_profile, dict):
    script = personalize_editorial_script(script, immersive_profile)

# Uma segunda sessão pode ter aberto a mesma run depois que esta sessão montou
# um contexto ainda vazio. Reconsulta somente nesse estado inicial, antes de
# gastar uma nova geração do modelo.
if not fresh_start and not messages and is_frame_script(script):
    repository = runtime_repository()
    if repository is not None:
        refreshed_context, refreshed_state, refreshed_messages = open_persistent_runtime(
            repository,
            user=user,
            package_id=PACKAGE_ID,
            package_version=context.package_version,
            restart=False,
            instance_id=context.instance_id,
        )
        if refreshed_messages:
            context, story_state, messages = (
                refreshed_context,
                refreshed_state,
                refreshed_messages,
            )
            save_runtime(user, context, story_state, messages)

if not story_state.finished:
    try:
        access = get_paid_run_access(secrets=st.secrets, user_id=user.user_id, package_id=PACKAGE_ID)
    except Exception as exc:
        log_editorial_exception("novel_v2_access", exc, user_id=user.user_id, package_id=PACKAGE_ID)
        st.error(f"Não foi possível verificar o acesso: {exc}")
        st.stop()
    if not access.allowed:
        return_to_library()

st.title(PACKAGE_TITLE)
st.caption(PACKAGE_SUBTITLE or "Novela interativa")

# No roteiro de quadros, a abertura é o primeiro quadro completo. Ela percorre
# exatamente o mesmo pipeline dos demais movimentos: geração, persistência,
# imagem e renderer. Não existe mais uma scene_opening separada para esse modo.
if not messages and is_frame_script(script):
    try:
        target_id, movement = first_frame_movement(script)
        assistant_text = generate_movement_text(
            movement=movement,
            user_name=profile_user_name(immersive_profile),
            profile=immersive_profile,
            messages=messages,
        )
        if not assistant_text:
            raise RuntimeError(OPERATIONAL_GENERATION_ERROR)
        context, story_state = persist_movement(
            user=user,
            context=context,
            state=story_state,
            messages=messages,
            target_id=target_id,
            movement=movement,
            assistant_text=assistant_text,
            profile=immersive_profile,
            input_source="opening_frame",
        )
        save_runtime(user, context, story_state, messages)
        st.rerun()
    except OpenRouterError as exc:
        log_editorial_exception("novel_v2_opening_generation", exc, user_id=user.user_id, package_id=PACKAGE_ID)
        st.error(OPERATIONAL_GENERATION_ERROR)
        st.stop()
    except Exception as exc:
        log_editorial_exception("novel_v2_opening_frame", exc, user_id=user.user_id, package_id=PACKAGE_ID)
        st.error(f"Não foi possível abrir a novela: {exc}")
        st.stop()

# Compatibilidade para roteiros V2 antigos que ainda usam abertura textual.
if not messages and not is_frame_script(script):
    opening = str(script.scene.get("introduction", "") or "").strip()
    if not opening:
        opening = str(script.raw.get("introduction", "") or "").strip()
    if opening:
        opening_metadata: dict[str, object] = {
            "character_id": "narrator",
            "scene_opening": True,
            "novel_v2": True,
            "editorial_node": "",
            "editorial_block": "",
        }
        opening_memory = persistent_profile_payload(immersive_profile)
        if opening_memory:
            opening_metadata["immersive_profile"] = opening_memory
        repository = runtime_repository()
        if repository is None:
            st.error("Google Sheets ficou indisponível ao registrar a abertura.")
            st.stop()
        try:
            context = persist_opening_message(
                repository,
                context=context,
                user=user,
                state=story_state,
                assistant_text=opening,
                assistant_metadata=opening_metadata,
            )
        except Exception as exc:
            log_editorial_exception("novel_v2_opening", exc, user_id=user.user_id, package_id=PACKAGE_ID)
            st.error(f"Não foi possível registrar a abertura: {exc}")
            st.stop()
        messages.append({"role": "assistant", "content": opening, **opening_metadata})
        save_runtime(user, context, story_state, messages)

with st.sidebar:
    st.subheader(PACKAGE_TITLE)
    st.caption(PACKAGE_SUBTITLE or "Novela interativa")
    current_id = current_movement_id(messages)
    st.write(f"Movimento: `{current_id or 'abertura'}`")
    if st.button("Retornar aos cards", width="stretch"):
        return_to_library()
    confirming_end = bool(st.session_state.get(END_CONFIRMATION_KEY, False))
    if not story_state.finished and not confirming_end:
        if st.button("Encerrar novela", width="stretch"):
            st.session_state[END_CONFIRMATION_KEY] = True
            st.rerun()
    elif not story_state.finished:
        st.warning("Encerrar irá gerar a necessidade de um novo pagamento. Continuar?")
        yes, no = st.columns(2)
        with yes:
            if st.button("Sim, encerrar", type="primary", width="stretch"):
                end_story_and_return(user)
        with no:
            if st.button("Cancelar", width="stretch"):
                st.session_state.pop(END_CONFIRMATION_KEY, None)
                st.rerun()

for message in current_assistant_messages(messages):
    if str(message.get("role", "assistant")) != "assistant":
        continue
    node = str(message.get("editorial_node") or message.get("beat_id") or "").strip()
    if node:
        try:
            render_editorial_scene_image(
                PACKAGE_ID,
                node,
                render_memory=False,
                ordered_beat_ids=tuple(script.beats),
            )
        except Exception as exc:
            log_editorial_exception("novel_v2_image", exc, package_id=PACKAGE_ID, node_id=node)
    presentation_role = "scene" if bool(message.get("scene_opening", False)) else "assistant"
    render_message(presentation_role, str(message.get("content", "")))

if story_state.finished:
    st.success("Fim da novela.")
    st.caption("Esta execução foi concluída normalmente.")
    if st.button("Voltar à biblioteca", type="primary", width="stretch"):
        return_to_library()
    st.stop()

if not st.button("Avançar", type="primary", width="stretch"):
    st.stop()

current_id = current_movement_id(messages)
target_id = next_movement_id(script, current_id)
if not target_id:
    story_state.finished = True
    try:
        finish_active_run(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            status="completed",
            ending_code="normal_completion",
        )
    except Exception as exc:
        log_editorial_exception("novel_v2_finish_without_target", exc, user_id=user.user_id, package_id=PACKAGE_ID)
    save_runtime(user, context, story_state, messages)
    st.rerun()

try:
    movement = movement_from_script(script, target_id)
    assistant_text = generate_movement_text(
        movement=movement,
        user_name=profile_user_name(immersive_profile),
        profile=immersive_profile,
        messages=messages,
    )
    if not assistant_text:
        raise RuntimeError(OPERATIONAL_GENERATION_ERROR)
except OpenRouterError as exc:
    log_editorial_exception(
        "novel_v2_generation",
        exc,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        target_id=target_id,
    )
    st.error(OPERATIONAL_GENERATION_ERROR)
    st.stop()
except Exception as exc:
    log_editorial_exception("novel_v2_resolve_movement", exc, package_id=PACKAGE_ID, target_id=target_id)
    st.error(OPERATIONAL_GENERATION_ERROR)
    st.stop()

try:
    context, story_state = persist_movement(
        user=user,
        context=context,
        state=story_state,
        messages=messages,
        target_id=target_id,
        movement=movement,
        assistant_text=assistant_text,
        profile=immersive_profile,
        input_source="advance_button",
    )
except Exception as exc:
    log_editorial_exception(
        "novel_v2_persist",
        exc,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        target_id=target_id,
    )
    st.error(f"Não foi possível registrar a cena: {exc}")
    st.stop()

save_runtime(user, context, story_state, messages)
st.rerun()
