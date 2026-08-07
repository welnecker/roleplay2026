from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

_ACTIVE_SELECTOR_KEY = "editorial_memory_active_selector_key"
_TURN_FACT_KEY = "_episodic_memory_turn"


def _persisted_turn_for_user_package(user_id: str, package_id: str) -> int:
    """Lê o turno somente do estado editorial do usuário e card atuais."""

    clean_user_id = str(user_id or "").strip()
    clean_package_id = str(package_id or "").strip()
    if not clean_user_id or not clean_package_id:
        return 0

    state_key = f"editorial:{clean_user_id}:{clean_package_id}:editorial_state"
    value = st.session_state.get(state_key)
    facts = getattr(value, "facts", None)
    if not isinstance(facts, Mapping):
        return 0
    try:
        return max(0, int(facts.get(_TURN_FACT_KEY, "0") or 0))
    except (TypeError, ValueError):
        return 0


def _selector_key(package_id: str, user_id: str) -> str:
    package = str(package_id or "").strip() or "editorial"
    user = str(user_id or "").strip() or "anonymous"
    turn = _persisted_turn_for_user_package(user, package)
    return f"editorial_memory_requested:{user}:{package}:{turn}"


def render_memory_selector(package_id: str, user_id: str = "") -> bool:
    """Renderiza uma escolha descartável, válida somente para o turno atual."""

    key = _selector_key(package_id, user_id)
    st.session_state[_ACTIVE_SELECTOR_KEY] = key
    selected = st.checkbox(
        "Mary deve se lembrar desta interação",
        key=key,
        value=False,
        help=(
            "Em uma ponte, cria um assunto que o roteiro poderá retomar e consumir. "
            "Em um beat canônico, cria uma lembrança cotidiana persistente."
        ),
    )
    if selected:
        st.caption("A resposta de Mary também fará parte da memória.")
    return bool(selected)


def peek_memory_request() -> bool:
    key = str(st.session_state.get(_ACTIVE_SELECTOR_KEY, "") or "").strip()
    return bool(key and st.session_state.get(key, False))


__all__ = ["peek_memory_request", "render_memory_selector"]
