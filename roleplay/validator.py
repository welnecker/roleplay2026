from __future__ import annotations

import re

from .interaction_control import set_interaction_action
from .models import Movement

_ACTION_PATTERN = re.compile(
    r"^\s*\[\[ACTION:(ADVANCE|STAY|END_NEGATIVE|END_HALLUCINATION|END_REFUSAL)\]\]\s*",
    flags=re.IGNORECASE,
)


def enforce_movement(response: str, movement: Movement) -> tuple[str, bool]:
    """Remove o controle interno e devolve apenas a fala visível de Mary."""

    value = str(response or "").strip()
    match = _ACTION_PATTERN.match(value)
    if match:
        set_interaction_action(match.group(1).casefold())
        visible = _ACTION_PATTERN.sub("", value, count=1).strip()
        if visible:
            return visible, False

    # Sem modelo/API, o conteúdo editorial continua sendo um fallback seguro e
    # o motor segue linearmente, preservando o comportamento local anterior.
    set_interaction_action("advance")
    return movement.content.strip(), True
