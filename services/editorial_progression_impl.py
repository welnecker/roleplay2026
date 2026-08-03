from __future__ import annotations

from dataclasses import replace

from services import editorial_runtime_impl as runtime_impl
from services.editorial_declared_decisions import decide_declared_special_turn
from services.editorial_declared_transitions import decide_declared_transition_turn
from services.editorial_followups import (
    editorial_followups_after,
    prepare_editorial_followups,
    render_editorial_followup_text,
    state_after_editorial_followup,
)
from services.editorial_message_policy import classify_contextual_editorial_message
from services.editorial_organic_turns import organic_editorial_turn
from services.editorial_response_policy import clean_editorial_progression_response
from services.editorial_routing import (
    routing_state_for_declared_skips,
    state_with_extracted_facts,
)
from services.editorial_runtime_impl import decide_turn as base_decide_turn
from services.editorial_runtime_types import (
    EditorialScript,
    EditorialState,
    EditorialTurn,
)
from services.editorial_turn_finalization import finalize_editorial_turn


def prepare_editorial_script(script: EditorialScript) -> EditorialScript:
    """Prepara políticas e pontes pertencentes ao próprio roteiro editorial."""

    prepare_editorial_followups(script)
    runtime_impl.classify_user_message = classify_contextual_editorial_message
    return script


def _finalize_declared(script: EditorialScript, turn: EditorialTurn) -> EditorialTurn:
    updated = EditorialState.from_dict(turn.state.to_dict())
    updated.facts["_organic_interstitial"] = "false"
    return finalize_editorial_turn(script, replace(turn, state=updated))


def decide_editorial_progression_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn:
    """Decide transições comuns e decisões declaradas pelo card."""

    original_facts = dict(state.facts)
    working_state = state_with_extracted_facts(state, user_text)

    organic = organic_editorial_turn(script, working_state, user_text)
    if organic is not None:
        return finalize_editorial_turn(script, organic)

    declared = decide_declared_transition_turn(
        script,
        working_state,
        user_text,
        base_decide=base_decide_turn,
        classify_message=classify_contextual_editorial_message,
    )
    if declared is not None:
        return _finalize_declared(script, declared)

    special = decide_declared_special_turn(
        script,
        working_state,
        user_text,
        base_decide=base_decide_turn,
        classify_message=classify_contextual_editorial_message,
    )
    if special is not None:
        return _finalize_declared(script, special)

    engagement = classify_contextual_editorial_message(user_text)
    routing_state = routing_state_for_declared_skips(
        script,
        working_state,
        engagement,
        original_facts=original_facts,
    )
    turn = base_decide_turn(script, routing_state, user_text)
    updated = EditorialState.from_dict(turn.state.to_dict())
    updated.facts["_organic_interstitial"] = "false"
    return finalize_editorial_turn(script, replace(turn, state=updated))
