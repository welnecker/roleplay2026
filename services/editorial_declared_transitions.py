from __future__ import annotations

import re
from typing import Any, Callable

from services.editorial_engine import TransitionRule, evaluate_transition_rules
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_semantic_intent import IntentResolution, resolve_semantic_intent


DecisionFunction = Callable[[EditorialScript, EditorialState, str], EditorialTurn]
ClassifierFunction = Callable[[str], str]


class _SafeFormat(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _deterministic_intent(classifiers: Any, user_text: str) -> IntentResolution:
    if not isinstance(classifiers, list) or not classifiers:
        return IntentResolution.unclear(source="no_declared_classifiers")
    value = " ".join(str(user_text or "").casefold().split())
    default_intent = "unclear"
    for classifier in classifiers:
        if not isinstance(classifier, dict):
            continue
        intent = str(classifier.get("intent", "") or "").strip()
        if not intent:
            continue
        if bool(classifier.get("default", False)):
            default_intent = intent
            continue
        contains = str(classifier.get("contains", "") or "")
        if contains and contains in value:
            return IntentResolution(
                intent=intent,
                confidence=1.0,
                evidence=contains,
                explicit_decision=intent in {"accept", "refuse", "postpone"},
                source="declared_contains",
            )
        patterns = classifier.get("patterns") or []
        if isinstance(patterns, list):
            for pattern in patterns:
                expression = str(pattern).strip()
                if not expression:
                    continue
                match = re.search(expression, value, flags=re.IGNORECASE)
                if match:
                    return IntentResolution(
                        intent=intent,
                        confidence=1.0,
                        evidence=match.group(0),
                        explicit_decision=intent in {"accept", "refuse", "postpone"},
                        source="declared_pattern",
                    )
    return IntentResolution(
        intent=default_intent,
        confidence=0.0 if default_intent == "unclear" else 1.0,
        evidence="",
        explicit_decision=False,
        source="declared_default",
    )


def _classify_intent(beat: dict[str, Any], classifiers: Any, user_text: str) -> IntentResolution:
    deterministic = _deterministic_intent(classifiers, user_text)
    if deterministic.intent != "unclear":
        return deterministic
    semantic = resolve_semantic_intent(beat, classifiers, user_text)
    if semantic.intent != "unclear":
        return semantic
    return IntentResolution(
        intent="unclear",
        confidence=max(deterministic.confidence, semantic.confidence),
        evidence=semantic.evidence,
        explicit_decision=False,
        source=semantic.source,
    )


def _dialogue_anchor(script: EditorialScript, beat_id: str) -> str:
    source = script.beats.get(beat_id) or script.endings.get(beat_id) or {}
    for unit in source.get("units", []) or []:
        if isinstance(unit, dict) and unit.get("kind") == "dialogue":
            return str(unit.get("anchor") or unit.get("text") or "")
    visible = source.get("visible_delivery") or {}
    return str(visible.get("text", "") if isinstance(visible, dict) else "")


def _render(value: str, *, intent: str, user_text: str, current_id: str) -> str:
    return str(value or "").format_map(
        _SafeFormat(
            intent=intent,
            user_text=str(user_text or ""),
            current_beat_id=current_id,
        )
    ).strip()


def _relationship(state: EditorialState) -> dict[str, int]:
    return {
        "interest": state.interest,
        "desire": state.desire,
        "trust": state.trust,
        "patience": state.patience,
    }


def _apply_effects(state: EditorialState, decision) -> EditorialState:
    updated = EditorialState.from_dict(state.to_dict())
    updated.facts.update({str(k): str(v) for k, v in decision.effects.facts.items()})
    for attribute, delta in decision.effects.relationship.items():
        if attribute not in {"interest", "desire", "trust", "patience"}:
            raise ValueError(f"Atributo de relacionamento desconhecido: {attribute!r}")
        setattr(updated, attribute, max(0, int(getattr(updated, attribute)) + int(delta)))
    return updated


def _record_intent(state: EditorialState, resolution: IntentResolution) -> None:
    state.facts["_last_user_intent"] = resolution.intent
    state.facts["_last_user_intent_source"] = resolution.source
    state.facts["_last_user_intent_confidence"] = f"{resolution.confidence:.3f}"
    state.facts["_last_user_intent_evidence"] = resolution.evidence
    state.facts["_last_user_explicit_decision"] = (
        "true" if resolution.explicit_decision else "false"
    )


def decide_declared_transition_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    base_decide: DecisionFunction,
    classify_message: ClassifierFunction,
) -> EditorialTurn | None:
    """Executa transições declaradas com interpretação semântica quando necessário."""

    current_id = state.node_id or script.first_beat_id
    beat = script.beats.get(current_id)
    if not isinstance(beat, dict):
        return None
    rules = beat.get("transition_rules") or ()
    classifiers = beat.get("intent_classifiers") or []
    if not rules or not classifiers:
        return None
    if not all(isinstance(rule, TransitionRule) for rule in rules):
        raise ValueError(f"Beat {current_id!r} possui transition_rules inválidas.")

    resolution = _classify_intent(beat, classifiers, user_text)
    intent = resolution.intent
    engagement = classify_message(user_text)
    decision = evaluate_transition_rules(
        tuple(rules),
        current_beat_id=current_id,
        intent=intent,
        engagement=engagement,
        facts=state.facts,
        relationship=_relationship(state),
    )
    if decision is None:
        return None

    legacy = beat.get("on_user") or {}
    legacy_target = str(
        legacy.get(engagement) or legacy.get("engaged") or beat.get("terminal_transition") or ""
    )
    if not decision.stay and decision.target_beat_id == legacy_target:
        turn = base_decide(script, state, user_text)
        updated = _apply_effects(turn.state, decision)
        _record_intent(updated, resolution)
        return EditorialTurn(
            engagement=turn.engagement,
            target_id=turn.target_id,
            visible_fallback=turn.visible_fallback,
            system_prompt=turn.system_prompt,
            state=updated,
            finished=turn.finished,
            run_status=turn.run_status,
            ending_code=turn.ending_code,
        )

    target_id = decision.target_beat_id
    if target_id not in script.beats and target_id not in script.endings:
        raise ValueError(f"Destino declarado inexistente: {target_id!r}")
    updated = _apply_effects(state, decision)
    updated.node_id = target_id
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    _record_intent(updated, resolution)

    fallback = _render(decision.fallback, intent=intent, user_text=user_text, current_id=current_id)
    if not fallback:
        fallback = _dialogue_anchor(script, target_id)
    prompt = _render(decision.prompt, intent=intent, user_text=user_text, current_id=current_id)
    return EditorialTurn(
        engagement=engagement,  # type: ignore[arg-type]
        target_id=target_id,
        visible_fallback=fallback,
        system_prompt=prompt,
        state=updated,
    )


__all__ = ["decide_declared_transition_turn"]
