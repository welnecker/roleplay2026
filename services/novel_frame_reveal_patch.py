from __future__ import annotations

from typing import Any

import streamlit as st

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
    clean = str(frame_id or "").strip()
    if clean:
        st.session_state[reveal_key(clean)] = 0


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
        return True

    frame_id = str(current.get("frame_id", "") or "").strip()
    count = max(0, int(current.get("entry_count", 0) or 0))
    if not frame_id or count <= 0:
        return True

    key = reveal_key(frame_id)
    if key not in st.session_state:
        # Quadro histórico/retomado: ele já está integralmente visível.
        return True

    index = reveal_index(frame_id, count)
    if index < count:
        st.session_state[key] = index + 1
        st.rerun()
        return False

    # Todas as entries já foram reveladas. Este clique pode chegar ao motor
    # narrativo e criar o próximo quadro.
    return True


def _persist_wrapper(*args: Any, **kwargs: Any):
    assert _original_persist_assistant_message is not None
    result = _original_persist_assistant_message(*args, **kwargs)

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
