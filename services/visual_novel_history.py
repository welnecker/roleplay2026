from __future__ import annotations

from collections.abc import Mapping, Sequence


def current_assistant_messages(
    messages: Sequence[Mapping[str, object]],
) -> tuple[Mapping[str, object], ...]:
    """Retorna apenas o quadro atual sem descartar o histórico persistido."""

    for message in reversed(messages):
        if str(message.get("role", "assistant")) == "assistant":
            return (message,)
    return ()


__all__ = ["current_assistant_messages"]
