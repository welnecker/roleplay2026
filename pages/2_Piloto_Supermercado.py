from __future__ import annotations

from pathlib import Path


# Compatibilidade transitória para links antigos do Streamlit.
_generic_player = Path(__file__).with_name("2_Historia_Editorial.py")
exec(
    compile(
        _generic_player.read_text(encoding="utf-8"),
        str(_generic_player),
        "exec",
    ),
    globals(),
    globals(),
)
