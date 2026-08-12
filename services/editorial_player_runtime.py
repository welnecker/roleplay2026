from __future__ import annotations

import time

import streamlit as st

from packages.models import InstalledStoryPackage
from persistence.factory import build_google_sheets_repository
from platform_core.auth import AuthenticatedUser
from roleplay.models import StoryState
from roleplay.openrouter import OpenRouterError, generate_response
from services.dialogue_presentation import (
    render_dialogue_html,
    with_scripted_thought_guidance,
)
from services.editorial_content import find_editorial_package, load_editorial_package
from services.editorial_diagnostics import (
    build_editorial_turn_diagnostics,
    log_editorial_exception,
    log_editorial_turn,
)
from services.editorial_metadata import (
    build_editorial_bridge_metadata,
    build_editorial_metadata,
    recover_editorial_state_payload,
)
from services.editorial_progression import (
    editorial_followups_after,
    state_after_editorial_followup,
)
from services.editorial_response_evaluator import (
    build_regeneration_prompt,
    build_semantic_evaluation_prompt,
    build_semantic_evaluation_request,
    evaluate_deterministic_response,
    merge_evaluations,
    parse_semantic_evaluation,
)
from services.editorial_runtime import (
    EditorialScript,
    EditorialState,
    clean_editorial_model_response,
    decide_editorial_turn,
    editorial_opening_text,
    editorial_scene_opening_text,
)
from services.editorial_scene_images import render_editorial_scene_image
from services.editorial_script_snapshot import (
    clear_script_snapshot as clear_script_snapshot_state,
    load_script_snapshot,
)
from services.editorial_transaction import (
    commit_editorial_turn,
    prepare_pending_editorial_turn,
)
from services.immersive_onboarding import (
    build_immersive_context,
    clear_immersive_profile,
    persistent_profile_payload,
    profile_key,
    recover_persistent_profile,
    render_immersive_onboarding,
    restore_profile_for_run,
)
from services.paid_run_access import get_paid_run_access, terminate_paid_access
from services.runtime_persistence import (
    RuntimePersistenceContext,
    open_persistent_runtime,
    persist_opening_message,
    persist_assistant_message,
    persist_turn,
)
from services.story_profile import (
    opening_with_required_name,
    personalize_editorial_script,
)
from ui_components import CARD_CSS


MODEL_DEFAULT = "google/gemini-3-flash-preview"
PAYMENT_QUOTA_WINDOW_SECONDS = 65.0
MAX_GENERATION_ATTEMPTS = 2
OPERATIONAL_GENERATION_ERROR = "Não foi possível gerar a resposta agora. Tente novamente."


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
CHARACTER_NAME = (
    PACKAGE.manifest.card.character_profile.name
    if PACKAGE.manifest.card.character_profile
    else PACKAGE_TITLE
)
CHARACTER_ID = CHARACTER_NAME.strip().casefold().replace(" ", "_") or "character"
END_CONFIRMATION_KEY = f"confirm_end:{PACKAGE_ID}"

st.set_page_config(page_title=PACKAGE_TITLE, page_icon="📖", layout="centered")
st.markdown(CARD_CSS, unsafe_allow_html=True)


def load_script(package_id: str) -> EditorialScript:
    """Lê e compila a versão vigente de ROTEIROS."""

    package = find_editorial_package(package_id)
    if package is None:
        raise RuntimeError(f"Pacote editorial não encontrado: {package_id}")
    return load_editorial_package(st.secrets, package)


def clear_script_snapshot(user_id: str) -> None:
    clear_script_snapshot_state(
        st.session_state, user_id=user_id, package_id=PACKAGE_ID
    )


def session_script(user: AuthenticatedUser, *, refresh: bool = False) -> EditorialScript:
    """Mantém um snapshot coerente durante a permanência na história.

    Reruns comuns reutilizam o objeto compilado. Nova entrada, novo pagamento ou
    encerramento removem a cópia e fazem a próxima abertura reler ROTEIROS.
    """

    return load_script_snapshot(
        st.session_state,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        loader=lambda: load_script(PACKAGE_ID),
        expected_type=EditorialScript,
        refresh=refresh,
    )


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


def recover_editorial_state(messages: list[dict[str, object]]) -> EditorialState:
    payload = recover_editorial_state_payload(messages)
    return EditorialState.from_dict(payload) if payload is not None else EditorialState()


def ensure_runtime(
    user: AuthenticatedUser,
    *,
    package_version: str,
    restart: bool = False,
) -> tuple[RuntimePersistenceContext, StoryState, list[dict[str, object]], EditorialState]:
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
        and isinstance(editorial_state, EditorialState)
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
    editorial_state: EditorialState,
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
    clear_script_snapshot(user.user_id)
    clear_immersive_profile(
        st.session_state, user_id=user.user_id, package_id=PACKAGE_ID
    )


def return_to_library() -> None:
    user = authenticated_user()
    if user is not None:
        clear_script_snapshot(user.user_id)
        clear_immersive_profile(
            st.session_state, user_id=user.user_id, package_id=PACKAGE_ID
        )
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
        log_editorial_exception(
            "terminate_paid_access",
            exc,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
        )
        st.error(f"Não foi possível encerrar a história: {exc}")
        return
    clear_session(user)
    st.session_state.started_packages.discard(PACKAGE_ID)
    st.session_state.pop("payment_access_ready", None)
    return_to_library()


def render_message(role: str, content: str) -> None:
    st.markdown(
        render_dialogue_html(role, content, character_name=CHARACTER_NAME),
        unsafe_allow_html=True,
    )


def render_current_scene(state: EditorialState) -> None:
    """Renderiza apoio visual sem interferir no input ou no motor narrativo."""

    try:
        render_editorial_scene_image(PACKAGE_ID, state.node_id)
    except Exception as exc:
        log_editorial_exception(
            "render_editorial_scene_image",
            exc,
            package_id=PACKAGE_ID,
            node_id=state.node_id,
        )
        st.caption("A imagem desta cena não pôde ser carregada.")


def advance_story_state(state: StoryState, *, finished: bool = False) -> StoryState:
    updated = state.copy()
    updated.step_index += 1
    updated.consumed_orders.append(updated.step_index)
    updated.finished = finished
    return updated


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
    script = session_script(user, refresh=fresh_start)
except Exception as exc:
    log_editorial_exception("load_editorial_script", exc, package_id=PACKAGE_ID)
    st.error(f"Não foi possível carregar o roteiro editorial: {exc}")
    st.stop()

try:
    context, story_state, messages, editorial_state = ensure_runtime(
        user,
        restart=fresh_start,
        package_version=str(script.raw.get("script_version", PACKAGE.manifest.version)),
    )
except Exception as exc:
    log_editorial_exception(
        "open_runtime",
        exc,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
    )
    st.error(f"Não foi possível abrir a história: {exc}")
    st.stop()

restore_profile_for_run(
    st.session_state,
    user_id=user.user_id,
    package_id=PACKAGE_ID,
    messages=messages,
)
if not render_immersive_onboarding(
    user_id=user.user_id,
    package_id=PACKAGE_ID,
    title=PACKAGE_TITLE,
    character_name=(
        PACKAGE.manifest.card.character_profile.name
        if PACKAGE.manifest.card.character_profile
        else PACKAGE_TITLE
    ),
    api_key=api_key,
    model=model,
):
    st.stop()
immersive_profile = st.session_state.get(profile_key(user.user_id, PACKAGE_ID))
if isinstance(immersive_profile, dict):
    script = personalize_editorial_script(script, immersive_profile)

if not editorial_state.finished and not story_state.finished:
    try:
        access = get_paid_run_access(
            secrets=st.secrets,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
        )
    except Exception as exc:
        log_editorial_exception(
            "check_paid_access",
            exc,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
        )
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
    scene_opening = editorial_scene_opening_text(script)
    opening = scene_opening or editorial_opening_text(script)
    if not scene_opening and isinstance(immersive_profile, dict):
        opening = opening_with_required_name(opening, immersive_profile)
    opening_editorial_state = EditorialState.from_dict(editorial_state.to_dict())
    opening_editorial_state.node_id = "" if scene_opening else script.first_beat_id
    opening_editorial_state.pending_next_beat_id = (
        script.first_beat_id if scene_opening else ""
    )
    opening_editorial_state.facts["_runtime_phase"] = "canonical"
    opening_metadata = build_editorial_metadata(
        node_id="" if scene_opening else script.first_beat_id,
        engagement="scene_opening" if scene_opening else "opening",
        state=opening_editorial_state.to_dict(),
        finished=False,
        run_status="active",
        ending_code="",
    )
    opening_metadata["character_id"] = "narrator" if scene_opening else CHARACTER_ID
    opening_metadata["scene_opening"] = bool(scene_opening)
    opening_metadata["editorial_block"] = str(
        (script.beats.get(script.first_beat_id) or {}).get("block_id", "") or ""
    )
    opening_memory = persistent_profile_payload(
        st.session_state.get(profile_key(user.user_id, PACKAGE_ID))
    )
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
        log_editorial_exception(
            "persist_opening_message",
            exc,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            node_id=script.first_beat_id,
        )
        st.error(f"Não foi possível registrar a abertura: {exc}")
        st.stop()
    messages.append({"role": "assistant", "content": opening, **opening_metadata})
    editorial_state = opening_editorial_state
    save_session(user, context, story_state, messages, editorial_state)
for message in messages:
    if str(message.get("role", "assistant")) == "assistant":
        message_node_id = str(
            message.get("editorial_node") or message.get("beat_id") or ""
        ).strip()
        if message_node_id:
            try:
                render_editorial_scene_image(
                    PACKAGE_ID,
                    message_node_id,
                    render_memory=False,
                )
            except Exception as exc:
                log_editorial_exception(
                    "render_editorial_message_image",
                    exc,
                    package_id=PACKAGE_ID,
                    node_id=message_node_id,
                )
    presentation_role = (
        "scene"
        if bool(message.get("scene_opening", False))
        else str(message.get("role", "assistant"))
    )
    render_message(presentation_role, str(message.get("content", "")))

if editorial_state.finished or story_state.finished:
    if editorial_state.run_status == "completed":
        st.success("História concluída.")
    else:
        st.info("A interação foi encerrada.")
    st.caption("A última fala foi registrada. Esta execução não aceita novas mensagens.")
    if st.button("Voltar à biblioteca", type="primary", use_container_width=True):
        return_to_library()
    st.stop()

last_message_node_id = ""
if messages and str(messages[-1].get("role", "")) == "assistant":
    last_message_node_id = str(
        messages[-1].get("editorial_node") or messages[-1].get("beat_id") or ""
    ).strip()
if last_message_node_id != editorial_state.node_id:
    render_current_scene(editorial_state)
else:
    # A imagem do beat já foi exibida junto da fala; mantém apenas o controle de memória.
    render_editorial_scene_image(PACKAGE_ID, "", user.user_id)
user_text = st.chat_input("Responda")
if not user_text:
    st.stop()

history = [
    {"role": str(item.get("role", "assistant")), "content": str(item.get("content", ""))}
    for item in messages[-12:]
]

try:
    proposed_turn = decide_editorial_turn(
        script,
        editorial_state,
        user_text,
        history=history,
    )
    pending = prepare_pending_editorial_turn(script, editorial_state, proposed_turn)
except Exception as exc:
    log_editorial_exception(
        "prepare_editorial_turn",
        exc,
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        node_id=editorial_state.node_id,
        pending_beat_id=editorial_state.pending_next_beat_id,
        user_text=user_text,
    )
    st.error("Não foi possível decidir o próximo movimento da história.")
    st.stop()

if not api_key:
    log_editorial_exception(
        "openrouter_not_configured",
        RuntimeError("OPENROUTER_API_KEY ausente"),
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        node_id=editorial_state.node_id,
        target_id=proposed_turn.target_id,
    )
    st.error(OPERATIONAL_GENERATION_ERROR)
    st.stop()

base_prompt = with_scripted_thought_guidance(
    pending.prompt,
    authored_thought=pending.context.authored_thought,
    character_name=CHARACTER_NAME,
)
private_context = build_immersive_context(
    st.session_state.get(profile_key(user.user_id, PACKAGE_ID))
)
evaluation_prompt = build_semantic_evaluation_prompt(pending.context)
raw_model_response = ""
assistant_text = ""
previous_violations: tuple[str, ...] = ()
final_violations: tuple[str, ...] = ()
attempts = 0

for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
    attempts = attempt
    current_violations: tuple[str, ...] = ()
    generation_prompt = (
        base_prompt
        if attempt == 1
        else build_regeneration_prompt(
            base_prompt=base_prompt,
            violations=previous_violations,
        )
    )
    try:
        raw_model_response = generate_response(
            api_key=api_key,
            model=model,
            system_prompt=generation_prompt + private_context,
            history=history,
            user_text=user_text,
            debug_logging=not bool(private_context),
        )
        candidate = clean_editorial_model_response(raw_model_response, "")
        deterministic = evaluate_deterministic_response(candidate, pending.context)
        semantic_raw = generate_response(
            api_key=api_key,
            model=model,
            system_prompt=evaluation_prompt,
            history=[],
            user_text=build_semantic_evaluation_request(
                user_text=user_text,
                candidate=candidate,
            ),
        )
        semantic = parse_semantic_evaluation(
            semantic_raw,
            candidate=candidate,
            context=pending.context,
        )
        combined = merge_evaluations(deterministic, semantic)
    except OpenRouterError as exc:
        log_editorial_exception(
            "openrouter_generation_or_evaluation",
            exc,
            user_id=user.user_id,
            package_id=PACKAGE_ID,
            node_id=editorial_state.node_id,
            target_id=proposed_turn.target_id,
            attempt=attempt,
        )
        st.error(OPERATIONAL_GENERATION_ERROR)
        st.stop()

    if combined.valid:
        assistant_text = candidate
        final_violations = ()
        break
    current_violations = combined.violations
    previous_violations = current_violations
    final_violations = current_violations

if not assistant_text:
    log_editorial_exception(
        "editorial_response_rejected",
        RuntimeError("Resposta rejeitada após regeneração controlada"),
        user_id=user.user_id,
        package_id=PACKAGE_ID,
        node_id=editorial_state.node_id,
        target_id=proposed_turn.target_id,
        attempts=attempts,
        violations=final_violations,
    )
    st.error(OPERATIONAL_GENERATION_ERROR)
    st.stop()

committed = commit_editorial_turn(pending, assistant_text)
turn = committed.turn
final_editorial_state = committed.state

diagnostics = build_editorial_turn_diagnostics(
    user_text=user_text,
    previous_state=editorial_state,
    turn=turn,
    raw_model_response=raw_model_response,
    final_response=assistant_text,
    fallback="",
    generation_error="",
    guard_reason="transactional_response_approved",
    repeated_recent_anchor=False,
    system_prompt=base_prompt,
)
diagnostics["generation_attempts"] = attempts
diagnostics["evaluation_violations"] = list(final_violations)
diagnostics["state_committed_after_approval"] = True
log_editorial_turn(diagnostics)

updated_story_state = advance_story_state(story_state, finished=turn.finished)
metadata = build_editorial_metadata(
    node_id=turn.target_id,
    engagement=turn.engagement,
    state=final_editorial_state.to_dict(),
    finished=turn.finished,
    run_status=turn.run_status,
    ending_code=turn.ending_code,
    diagnostics=diagnostics,
)
metadata["character_id"] = CHARACTER_ID
metadata["editorial_block"] = str(
    (script.beats.get(turn.target_id) or {}).get("block_id", "") or ""
)
immersive_memory = persistent_profile_payload(
    st.session_state.get(profile_key(user.user_id, PACKAGE_ID))
)
if immersive_memory and recover_persistent_profile(messages) is None:
    metadata["immersive_profile"] = immersive_memory
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

    is_organic_interstitial = final_editorial_state.facts.get("_organic_interstitial") == "true"
    if not is_organic_interstitial:
        for followup in editorial_followups_after(turn.target_id):
            final_editorial_state = state_after_editorial_followup(
                final_editorial_state,
                followup,
            )
            updated_story_state = advance_story_state(updated_story_state)
            followup_metadata = build_editorial_bridge_metadata(
                node_id=str(followup["target_id"]),
                state=final_editorial_state.to_dict(),
            )
            followup_metadata["character_id"] = CHARACTER_ID
            followup_metadata["editorial_block"] = str(
                (script.beats.get(str(followup["target_id"])) or {}).get(
                    "block_id", ""
                )
                or ""
            )
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
    log_editorial_exception(
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
st.rerun()
