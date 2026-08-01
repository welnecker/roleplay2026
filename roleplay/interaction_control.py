from __future__ import annotations

from contextvars import ContextVar
from typing import Literal

InteractionAction = Literal[
    "advance",
    "stay",
    "end_negative",
    "end_hallucination",
    "end_refusal",
]

_ACTION: ContextVar[InteractionAction] = ContextVar("roleplay_interaction_action", default="advance")


def set_interaction_action(action: str) -> InteractionAction:
    normalized = str(action or "").strip().casefold()
    allowed: set[str] = {
        "advance",
        "stay",
        "end_negative",
        "end_hallucination",
        "end_refusal",
    }
    resolved: InteractionAction = normalized if normalized in allowed else "advance"  # type: ignore[assignment]
    _ACTION.set(resolved)
    return resolved


def consume_interaction_action() -> InteractionAction:
    action = _ACTION.get()
    _ACTION.set("advance")
    return action
