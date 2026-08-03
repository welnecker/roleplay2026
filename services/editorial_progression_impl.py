from __future__ import annotations

from dataclasses import replace

from services import editorial_progression_legacy as _legacy
from services.editorial_declared_decisions import decide_declared_special_turn
from services.editorial_runtime_impl import PilotScript, PilotState, PilotTurn


render_automatic_followup_text = _legacy.render_automatic_followup_text
prepare_supermarket_script_v2 = _legacy.prepare_supermarket_script_v2
classify_contextual_user_message = _legacy.classify_contextual_user_message
automatic_followups_after = _legacy.automatic_followups_after
state_after_automatic_followup = _legacy.state_after_automatic_followup
clean_supermarket_script_v2_response = _legacy.clean_supermarket_script_v2_response


def decide_supermarket_script_v2_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Decide transições comuns e decisões especiais declaradas pelo card."""

    original_facts = dict(state.facts)
    working_state = _legacy._state_with_extracted_facts(state, user_text)

    organic = _legacy._organic_slack_turn(script, working_state, user_text)
    if organic is not None:
        return _legacy._finalize_turn(script, organic)

    special = decide_declared_special_turn(
        script,
        working_state,
        user_text,
        base_decide=_legacy.base_decide_turn,
        classify_message=classify_contextual_user_message,
    )
    if special is not None:
        updated = PilotState.from_dict(special.state.to_dict())
        updated.facts["_organic_interstitial"] = "false"
        return _legacy._finalize_turn(script, replace(special, state=updated))

    engagement = classify_contextual_user_message(user_text)
    routing_state = _legacy._routing_state_for_declared_skips(
        script,
        working_state,
        engagement,
        original_facts=original_facts,
    )
    turn = _legacy.base_decide_turn(script, routing_state, user_text)
    updated = PilotState.from_dict(turn.state.to_dict())
    updated.facts["_organic_interstitial"] = "false"
    return _legacy._finalize_turn(script, replace(turn, state=updated))
