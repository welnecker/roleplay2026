from __future__ import annotations

import streamlit as st

_MEMORY_REQUEST_KEY = "editorial_memory_requested"


def render_memory_selector() -> bool:
    """Exibe uma única escolha; o runtime deriva o tipo pela fase estrutural."""

    selected = st.checkbox(
        "Mary deve se lembrar desta interação",
        key=_MEMORY_REQUEST_KEY,
        help=(
            "Em uma ponte, cria um assunto que o roteiro poderá retomar e consumir. "
            "Em um beat canônico, cria uma lembrança cotidiana persistente."
        ),
    )
    if selected:
        st.caption(
            "A resposta de Mary também fará parte da memória. "
            "O tipo será definido automaticamente pelo roteiro."
        )
    return bool(selected)


def peek_memory_request() -> bool:
    return bool(st.session_state.get(_MEMORY_REQUEST_KEY, False))


def clear_memory_request() -> None:
    st.session_state[_MEMORY_REQUEST_KEY] = False


__all__ = [
    "clear_memory_request",
    "peek_memory_request",
    "render_memory_selector",
]
