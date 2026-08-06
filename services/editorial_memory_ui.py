from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

_ACTIVE_SELECTOR_KEY = "editorial_memory_active_selector_key"
_TURN_FACT_KEY = "_episodic_memory_turn"


def _persisted_turn_for_package(package_id: str) -> int:
    """Lê somente o turno do estado editorial persistido do card atual."""

    suffix = f":{str(package_id or '').strip()}:editorial_state"
    values = (
        value
        for key, value in st.session_state.items()
        if str(key).endswith(suffix)
    )
    for value in values:
        facts = getattr(value, "facts", None)
        if not isinstance(facts, Mapping):
            continue
        try:
            return max(0, int(facts.get(_TURN_FACT_KEY, "0") or 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _selector_key(package_id: str) -> str:
    package = str(package_id or "").strip() or "editorial"
    turn = _persisted_turn_for_package(package)
    return f"editorial_memory_requested:{package}:{turn}"


def render_memory_selector(package_id: str) -> bool:
    """Renderiza uma escolha descartável, válida somente para o turno atual."""

    key = _selector_key(package_id)
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
