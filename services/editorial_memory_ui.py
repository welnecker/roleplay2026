from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

_MEMORY_REQUEST_KEY = "editorial_memory_requested"
_RESET_PENDING_KEY = "editorial_memory_reset_pending"
_MEMORY_FACT_KEYS = (
    "_continuity_memories_json",
    "_relationship_recollections_json",
)


def _reset_target_is_persisted(target: Mapping[str, str]) -> bool:
    """Confirma que a memória consolidada já chegou ao estado durável da sessão."""

    for value in st.session_state.values():
        facts = getattr(value, "facts", None)
        if not isinstance(facts, Mapping):
            continue
        if all(str(facts.get(key, "") or "") == expected for key, expected in target.items()):
            return True
    return False


def render_memory_selector() -> bool:
    # O reset só ocorre em um rerun no qual o estado já persistido contém a
    # memória consolidada. Em falha de persistência, a seleção permanece ativa
    # para que o usuário possa reenviar a interação sem perder sua escolha.
    pending = st.session_state.get(_RESET_PENDING_KEY)
    if isinstance(pending, Mapping) and _reset_target_is_persisted(pending):
        st.session_state.pop(_RESET_PENDING_KEY, None)
        st.session_state.pop(_MEMORY_REQUEST_KEY, None)

    selected = st.checkbox(
        "Mary deve se lembrar desta interação",
        key=_MEMORY_REQUEST_KEY,
        help=(
            "Em uma ponte, cria um assunto que o roteiro poderá retomar e consumir. "
            "Em um beat canônico, cria uma lembrança cotidiana persistente."
        ),
    )
    if selected:
        st.caption("A resposta de Mary também fará parte da memória.")
    return bool(selected)


def peek_memory_request() -> bool:
    return bool(st.session_state.get(_MEMORY_REQUEST_KEY, False))


def clear_memory_request(facts: Mapping[str, str]) -> None:
    """Agenda o reset condicionado à confirmação do estado persistido."""

    st.session_state[_RESET_PENDING_KEY] = {
        key: str(facts.get(key, "") or "")
        for key in _MEMORY_FACT_KEYS
    }


__all__ = ["clear_memory_request", "peek_memory_request", "render_memory_selector"]
