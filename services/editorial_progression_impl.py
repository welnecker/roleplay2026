from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from services import editorial_runtime_impl as runtime_impl
from services.editorial_bridge import (
    advance_authored_bridge_turn,
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
from services.editorial_resolved_topics import apply_resolved_topics
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


def _runtime_policy(script: EditorialScript) -> dict[str, Any]:
    direct = script.raw.get("runtime_policy") or {}
    if isinstance(direct, dict) and direct:
        return direct
    legacy = script.raw.get("organic_slack") or {}
    return legacy if isinstance(legacy, dict) else {}


def _word_count(text: str) -> int:
    return len(re.findall(r"[^\W_]+", str(text or ""), flags=re.UNICODE))


def _matches_scope(
    script: EditorialScript,
    state: EditorialState,
    policy: dict[str, Any],
) -> bool:
    beat_id = str(state.node_id or script.first_beat_id).strip()
    beat = script.beats.get(beat_id) or {}
    block_id = str(beat.get("block_id", "") or "").strip()
    beat_ids = {str(item).strip() for item in policy.get("beat_ids", []) or []}
    block_ids = {str(item).strip() for item in policy.get("block_ids", []) or []}
    prefixes = tuple(
        str(item).strip()
        for item in policy.get("beat_prefixes", []) or []
        if str(item).strip()
    )
    if not beat_ids and not block_ids and not prefixes:
        return True
    return beat_id in beat_ids or block_id in block_ids or any(
        beat_id.startswith(prefix) for prefix in prefixes
    )


def _contextual_bridge_allowed(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> bool:
    """Aplica seleção contextual somente ao escopo declarado pelo card.

    Fora desse escopo, a política histórica de ponte obrigatória permanece
    intacta. Dentro dele, respostas breves avançam; perguntas e contribuições
    substantivas podem respirar.
    """

    policy = _runtime_policy(script).get("bridge_selection") or {}
    if not isinstance(policy, dict) or not policy:
        return True
    if not _matches_scope(script, state, policy):
        return True
    mode = str(policy.get("mode", "always") or "always").strip()
    if mode != "contextual":
        return True

    maximum_direct_words = max(0, int(policy.get("direct_max_words", 4) or 4))
    value = str(user_text or "").strip()
    if "?" in value:
        return True
    return _word_count(value) > maximum_direct_words


def _apply_bridge_continuity(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> EditorialTurn:
    if str(turn.state.facts.get("_runtime_phase", "") or "") != "bridge":
        return turn

    policy = _runtime_policy(script).get("bridge_continuity") or {}
    if not isinstance(policy, dict) or not policy or not _matches_scope(script, previous_state, policy):
        return turn

    instructions = [
        "CONTRATO DE CONTINUIDADE DA PONTE:",
        "- A ponte pertence integralmente à mesma cena e deve responder ao conteúdo novo do usuário.",
        "- Não recite, reencene nem prolongue o movimento já consumido na origem.",
        "- Não execute nem parafraseie o movimento reservado ao destino.",
        "- Não use explicação, resumo ou fala genérica apenas para ocupar um turno.",
    ]
    if bool(policy.get("preserve_intensity", False)):
        instructions.extend(
            (
                "- Preserve a intensidade, o ritmo, o vocabulário e a dinâmica vigentes na cena.",
                "- Não suavize artificialmente o tom para adiar o próximo beat.",
            )
        )
    if bool(policy.get("allow_expressive_freedom", False)):
        instructions.append(
            "- Há liberdade expressiva dentro das fronteiras da origem e do destino, sem copiar a linha canônica."
        )
    return replace(
        turn,
        system_prompt=f"{turn.system_prompt.strip()}\n\n" + "\n".join(instructions),
    )


def _recover_unqualified_ending(
    script: EditorialScript,
    previous_state: EditorialState,
    user_text: str,
    turn: EditorialTurn,
) -> EditorialTurn:
    """Reavalia somente endings contraditos por sinais explícitos de continuidade."""

    policy = _runtime_policy(script).get("qualified_endings") or {}
    if not isinstance(policy, dict) or not policy or not turn.finished:
        return turn

    protected_codes = {
        str(item).strip()
        for item in policy.get("ending_codes", []) or []
        if str(item).strip()
    }
    ambiguous = {
        str(item).strip()
        for item in policy.get("ambiguous_engagements", []) or []
        if str(item).strip()
    }
    continue_intents = {
        str(item).strip()
        for item in policy.get("continuation_intents", []) or []
        if str(item).strip()
    }
    continue_routes = {
        str(item).strip()
        for item in policy.get("continuation_routes", []) or []
        if str(item).strip()
    }

    facts = previous_state.facts
    intent = str(facts.get("_last_user_intent", "") or "").strip()
    route = str(facts.get("_contextual_route", "") or "").strip()
    if protected_codes and turn.ending_code not in protected_codes:
        return turn
    if ambiguous and turn.engagement not in ambiguous:
        return turn
    if continue_intents and intent not in continue_intents:
        return turn
    if continue_routes and route not in continue_routes:
        return turn

    retry_state = EditorialState.from_dict(previous_state.to_dict())
    retry_state.recent_engagement = [
        item for item in retry_state.recent_engagement if item not in ambiguous
    ]
    retry_state.finished = False
    retry_state.run_status = "active"
    retry_state.ending_code = ""
    recovered = base_decide_turn(script, retry_state, user_text)
    if recovered.finished:
        return turn
    recovered_state = EditorialState.from_dict(recovered.state.to_dict())
    recovered_state.facts["_qualified_ending_recovered"] = "true"
    return replace(recovered, state=recovered_state)


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
    qualified = _recover_unqualified_ending(script, previous_state, user_text, turn)
    resolved = apply_resolved_topics(script, previous_state, qualified)
    prepared = (
        create_bridge_turn(script, previous_state, resolved, user_text)
        if bridge_allowed and _contextual_bridge_allowed(script, previous_state, user_text)
        else resolved
    )
    prepared = _apply_bridge_continuity(script, previous_state, prepared)
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
    if releasing_bridge:
        bridge_state = state_with_extracted_facts(state, user_text)
        yard_turn = decide_terminal_yard_turn(
            script,
            bridge_state,
            user_text,
            base_decide=base_decide_turn,
            classify_message=classify_contextual_editorial_message,
        )
        if yard_turn is not None:
            return _finalize(script, yard_turn)
        continuation = advance_authored_bridge_turn(
            script,
            bridge_state,
            user_text,
            engagement=classify_contextual_editorial_message(user_text),
        )
        if continuation is not None:
            return _finalize(script, continuation)

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
        routing_state,
        turn,
        user_text,
        bridge_allowed=bridge_enabled and not releasing_bridge,
    )
