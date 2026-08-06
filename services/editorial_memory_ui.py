from __future__ import annotations

import streamlit as st

_MEMORY_REQUEST_KEY = "editorial_memory_requested"
_RESET_PENDING_KEY = "editorial_memory_reset_pending"


def render_memory_selector() -> bool:
    # A seleção pertence somente ao envio anterior. O reset é agendado apenas
    # depois que a persistência daquele turno termina com sucesso e é aplicado
    # antes de recriar o widget no rerun seguinte.
    if bool(st.session_state.pop(_RESET_PENDING_KEY, False)):
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


def schedule_memory_selector_reset() -> None:
    """Faz a próxima interação começar desmarcada após persistência bem-sucedida."""

    st.session_state[_RESET_PENDING_KEY] = True


__all__ = ["peek_memory_request", "render_memory_selector", "schedule_memory_selector_reset"]
