from __future__ import annotations

from collections.abc import Mapping, Sequence

VISIBLE_FRAME_LIMIT = 5


def current_assistant_messages(
    messages: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    """Retorna a janela visual recente sem descartar o histórico persistido."""

    assistant_messages = tuple(
        message
        for message in messages
        if str(message.get("role", "assistant")) == "assistant"
    )
    return assistant_messages[-VISIBLE_FRAME_LIMIT:]


__all__ = ["VISIBLE_FRAME_LIMIT", "current_assistant_messages"]
