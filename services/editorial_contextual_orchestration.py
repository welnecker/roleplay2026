from __future__ import annotations

from collections.abc import Callable

from services.editorial_contextual_destination import (
    ContextualDestination,
    build_contextual_classification_prompt,
    build_contextual_classification_request,
    contextual_classification_required,
    current_interaction_context,
    parse_contextual_destination,
    state_with_contextual_destination,
)
from services.editorial_runtime_types import EditorialScript, EditorialState


ClassifierCall = Callable[[str, str], str]


def classify_contextual_destination_for_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    classifier_call: ClassifierCall,
) -> tuple[EditorialState, ContextualDestination]:
    """Classifica uma vez e grava a decisão validada no estado transitório.

    O classificador recebe apenas o contrato contextual e a fala do usuário.
    IDs de beats, pátios e endings permanecem exclusivamente no runtime.
    """

    context = current_interaction_context(script, state)
    if not contextual_classification_required(context):
        destination = ContextualDestination(reason="contextual_classification_not_required")
        return state_with_contextual_destination(state, destination), destination

    raw = classifier_call(
        build_contextual_classification_prompt(context),
        build_contextual_classification_request(user_text),
    )
    destination = parse_contextual_destination(raw, context)
    return state_with_contextual_destination(state, destination), destination


__all__ = ["ClassifierCall", "classify_contextual_destination_for_turn"]
