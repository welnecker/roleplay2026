from __future__ import annotations

from typing import Any

import streamlit as st

from narrative_v2.repository import RuntimeConflictError

_CURRENT_KEY = "novel_frame_reveal:current"
_PREFIX = "novel_frame_reveal:index:"
_installed = False
_original_button = None
_original_persist_assistant_message = None


def reveal_key(frame_id: str) -> str:
    return f"{_PREFIX}{str(frame_id or '').strip()}"


def set_current_frame(frame_id: str, entry_count: int) -> None:
    clean = str(frame_id or "").strip()
    if not clean:
        return
    st.session_state[_CURRENT_KEY] = {
        "frame_id": clean,
        "entry_count": max(0, int(entry_count or 0)),
    }


def reveal_index(frame_id: str, entry_count: int) -> int:
    """Quadros sem estado explícito são históricos e aparecem completos."""

    clean = str(frame_id or "").strip()
    count = max(0, int(entry_count or 0))
    if not clean:
        return count
    key = reveal_key(clean)
    if key not in st.session_state:
        return count
    try:
        return max(0, min(count, int(st.session_state.get(key, 0) or 0)))
    except (TypeError, ValueError):
        return 0


def start_frame_reveal(frame_id: str) -> None:
    """Inicia um quadro novo já exibindo seu primeiro card.

    O total real de cards só é conhecido na renderização. Guardar ``1`` aqui é
    seguro porque ``reveal_index`` limita o valor ao ``entry_count``. Assim um
    quadro com N cards exige exatamente N cliques em Avançar para chegar ao
    próximo quadro: o primeiro card nasce com a cena, N-1 cliques revelam os
    demais e o clique N avança a narrativa.
    """

    clean = str(frame_id or "").strip()
    if clean:
        st.session_state[reveal_key(clean)] = 1


def _sequence(messages: list[dict[str, object]]) -> int:
    values = [
        int(item.get("sequence", 0) or 0)
        for item in messages
        if int(item.get("sequence", 0) or 0) > 0
    ]
    return max(values, default=0)


def _synchronize_remote_run(*, force: bool = False) -> bool:
    """Adota o estado persistido quando outra instancia avançou a mesma run.

    O Google Sheets continua sendo a autoridade. A sessão Streamlit local apenas
    substitui context/state/messages quando encontra uma sequência mais nova.
    ``force`` é usado depois de RuntimeConflictError, quando já sabemos que houve
    uma corrida de escrita.
    """

    from persistence.factory import build_google_sheets_repository
    from platform_core.auth import AuthenticatedUser
    from services.runtime_persistence import RuntimePersistenceContext, restore_story_state

    user = st.session_state.get("authenticated_user")
    if not isinstance(user, AuthenticatedUser):
        return False
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        return False

    prefix = f"novel_v2:{user.user_id}:{package_id}"
    context_key = f"{prefix}:context"
    state_key = f"{prefix}:story_state"
    messages_key = f"{prefix}:messages"
    context = st.session_state.get(context_key)
    local_messages = st.session_state.get(messages_key)
    if not isinstance(context, RuntimePersistenceContext) or context.run is None:
        return False
    if not isinstance(local_messages, list):
        return False

    repository = build_google_sheets_repository(st.secrets)
    if repository is None:
        return False
    persisted = repository.list_interactions(run_id=context.run.run_id, limit=500)
    if not persisted:
        return False

    persisted_sequence = _sequence(persisted)
    local_sequence = _sequence(local_messages)
    if not force and persisted_sequence <= local_sequence:
        return False
    if force and persisted_sequence < local_sequence:
        return False

    run = repository.get_run(run_id=context.run.run_id) or context.run
    state = None
    for message in reversed(persisted):
        raw_state = message.get("_story_state")
        if isinstance(raw_state, dict):
            state = restore_story_state(raw_state)
            break
    if state is None:
        state = st.session_state.get(state_key)
    if state is None:
        return False

    synced_context = RuntimePersistenceContext(
        package_id=context.package_id,
        package_version=context.package_version,
        run=run,
        session=context.session,
        instance_id=context.instance_id,
        next_sequence=persisted_sequence + 1,
    )
    st.session_state[context_key] = synced_context
    st.session_state[state_key] = state
    st.session_state[messages_key] = persisted
    return True


def _button_wrapper(*args: Any, **kwargs: Any) -> bool:
    assert _original_button is not None
    clicked = bool(_original_button(*args, **kwargs))
    if not clicked:
        return False

    label = str(args[0] if args else kwargs.get("label", "") or "").strip()
    if label != "Avançar":
        return True

    current = st.session_state.get(_CURRENT_KEY)
    if not isinstance(current, dict):
        if _synchronize_remote_run():
            st.rerun()
        return True

    frame_id = str(current.get("frame_id", "") or "").strip()
    count = max(0, int(current.get("entry_count", 0) or 0))
    if not frame_id or count <= 0:
        if _synchronize_remote_run():
            st.rerun()
        return True

    key = reveal_key(frame_id)
    if key not in st.session_state:
        # Quadro histórico/retomado: antes de avançar, verifica se outra
        # instancia já mudou a posição persistida da run.
        if _synchronize_remote_run():
            st.rerun()
        return True

    index = reveal_index(frame_id, count)
    if index < count:
        st.session_state[key] = index + 1
        st.rerun()
        return False

    # Todas as entries já foram reveladas. Antes de gerar outro quadro, adota
    # qualquer avanço que tenha acontecido em celular/desktop paralelo.
    if _synchronize_remote_run():
        st.rerun()
        return False
    return True


def _persist_wrapper(*args: Any, **kwargs: Any):
    assert _original_persist_assistant_message is not None
    try:
        result = _original_persist_assistant_message(*args, **kwargs)
    except RuntimeConflictError:
        # Uma segunda instancia venceu a corrida. O conteúdo já persistido é a
        # autoridade: sincroniza e interrompe este rerun antes que o player
        # acrescente sua geração local divergente à memória da sessão.
        if _synchronize_remote_run(force=True):
            st.rerun()
        raise

    metadata = kwargs.get("assistant_metadata")
    if isinstance(metadata, dict) and bool(metadata.get("novel_frame", False)):
        frame_id = str(metadata.get("editorial_node", "") or "").strip()
        if frame_id:
            start_frame_reveal(frame_id)
    return result


def install() -> None:
    global _installed, _original_button, _original_persist_assistant_message
    if _installed:
        return

    from services import runtime_persistence

    _original_button = st.button
    _original_persist_assistant_message = runtime_persistence.persist_assistant_message
    st.button = _button_wrapper
    runtime_persistence.persist_assistant_message = _persist_wrapper
    _installed = True


__all__ = [
    "install",
    "reveal_index",
    "reveal_key",
    "set_current_frame",
    "start_frame_reveal",
]
