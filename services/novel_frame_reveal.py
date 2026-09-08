"""Compatibilidade do backend com o contrato compartilhado de quadros V2."""

from roleplay_shared.novel_frame_reveal import (
    frame_entry_count,
    frame_id,
    frame_sections,
    is_frame_content,
    normalize_frame_markers,
    reveal_complete,
    reveal_frame_content,
)

__all__ = [
    "frame_entry_count",
    "frame_id",
    "frame_sections",
    "is_frame_content",
    "normalize_frame_markers",
    "reveal_complete",
    "reveal_frame_content",
]
