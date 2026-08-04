from __future__ import annotations

from dataclasses import replace

from services import editorial_runtime_impl as runtime_impl
from services.editorial_bridge import (
    bridge_active,
    bridge_enabled_for_beat,
    bridge_policy,
    create_bridge_turn,
    release_bridge_state,
)
from services.editorial_contextual_destination import decide_contextual_destination_turn
from services.editorial_declared_decisions import decide_declared_special_turn
from services.editorial_declared_transitions import decide_declared_transition_turn
from services.editorial_followups import (
    activate_editorial_followups,
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
from services.editorial_terminal_yard import decide_terminal_yard_turn
from services.editorial_turn_finalization import finalize_editorial_turn


def prepare_editorial_script(script: EditorialScript) -> EditorialScript:
    """Prepara políticas e estruturas pertencentes ao próprio roteiro editorial."""

    prepare_editorial_followups(script)
    runtime_impl.classify_user_message = classify_contextual_editorial_message
    return script


def _finalize(script: EditorialScript, turn: EditorialTurn, *, organic: bool = False) -> EditorialTurn:
    updated = EditorialState.from_dict(turn.state.to_dict())
    if bridge_policy(script):
        updated.facts.pop("_organic_interstitial", None)
        updated.interstitial_turns = 0
    else:
        updated.facts["_organic_interstitial"] = "true" if organic else "false"
    return finalize_editorial_turn(script, replace(turn, state=updated))


def _bridge_or_finalize(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
    user_text: str,
    *,
    bridge_allowed: bool,
) -> EditorialTurn:
    prepared = (
        create_bridge_turn(script, previous_state, turn, user_text)
        if bridge_allowed
        else turn
    )
    return _finalize(script, prepared)


def decide_editorial_progression_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn:
    """Decide pátio, destino contextual, ponte opt-in e progressão canônica."""

    activate_editorial_followups(script)
    original_state = EditorialState.from_dict(state.to_dict())
    original_facts = dict(state.facts)
    releasing_bridge = bridge_active(state)
    bridge_enabled = bridge_enabled_for_beat(
        script,
        state.node_id or script.first_beat_id,
    )
    base_state = release_bridge_state(script, state) if releasing_bridge else state
    working_state = state_with_extracted_facts(base_state, user_text)

    yard_turn = decide_terminal_yard_turn(
        script,
        working_state,
        user_text,
        base_decide=base_decide_turn,
        classify_message=classify_contextual_editorial_message,
    )
    if yard_turn is not None:
        return _finalize(script, yard_turn)

    contextual = decide_contextual_destination_turn(script, working_state, user_text)
    if contextual is not None:
        return _finalize(script, contextual)

    # Cards ainda não migrados mantêm integralmente a folga orgânica antiga.
    # Na ponte estrutural opt-in, ela é substituída pela nova fase para não haver
    # duas máquinas intermediárias concorrentes.
    if not bridge_enabled and not releasing_bridge:
        organic = organic_editorial_turn(script, working_state, user_text)
        if organic is not None:
            return _finalize(script, organic, organic=True)

    declared = decide_declared_transition_turn(
        script,
        working_state,
        user_text,
        base_decide=base_decide_turn,
        classify_message=classify_contextual_editorial_message,
    )
    if declared is not None:
        return _bridge_or_finalize(
            script,
            original_state,
            declared,
            user_text,
            bridge_allowed=bridge_enabled and not releasing_bridge,
        )

    special = decide_declared_special_turn(
        script,
        working_state,
        user_text,
        base_decide=base_decide_turn,
        classify_message=classify_contextual_editorial_message,
    )
    if special is not None:
        return _bridge_or_finalize(
            script,
            original_state,
            special,
            user_text,
            bridge_allowed=bridge_enabled and not releasing_bridge,
        )

    engagement = classify_contextual_editorial_message(user_text)
    routing_state = routing_state_for_declared_skips(
        script,
        working_state,
        engagement,
        original_facts=original_facts,
    )
    turn = base_decide_turn(script, routing_state, user_text)
    return _bridge_or_finalize(
        script,
        original_state,
        turn,
        user_text,
        bridge_allowed=bridge_enabled and not releasing_bridge,
    )
