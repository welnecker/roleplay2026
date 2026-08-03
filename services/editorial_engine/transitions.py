from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.editorial_engine.models import (
    NarrativeEffect,
    TransitionCondition,
    TransitionDecision,
    TransitionEffects,
    TransitionRule,
)


def _string_mapping(value: Any, *, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} deve ser um mapa.")
    return {str(key): str(item) for key, item in value.items()}


def _integer_mapping(value: Any, *, field_name: str) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} deve ser um mapa.")
    try:
        return {str(key): int(item) for key, item in value.items()}
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} aceita somente valores inteiros.") from exc


def _string_tuple(value: Any, *, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} deve ser uma lista.")
    return tuple(str(item).strip() for item in value if str(item).strip())


def _compile_declared_rule(raw: Any, index: int) -> TransitionRule:
    if not isinstance(raw, Mapping):
        raise ValueError("Cada item de transitions deve ser um mapa.")
    condition_raw = raw.get("when") or {}
    effects_raw = raw.get("effects") or {}
    narrative_raw = raw.get("narrative_effect") or {}
    if not isinstance(condition_raw, Mapping):
        raise ValueError("when deve ser um mapa.")
    if not isinstance(effects_raw, Mapping):
        raise ValueError("effects deve ser um mapa.")
    if not isinstance(narrative_raw, Mapping):
        raise ValueError("narrative_effect deve ser um mapa.")

    transition_id = str(raw.get("id", "") or "").strip() or f"transition_{index + 1}"
    next_beat_id = str(raw.get("next", "") or "").strip()
    stay = bool(raw.get("stay", False))
    condition = TransitionCondition(
        intent=str(condition_raw.get("intent", "") or "").strip(),
        engagement=str(condition_raw.get("engagement", "") or "").strip(),
        facts=_string_mapping(condition_raw.get("facts"), field_name="when.facts"),
        relationship=_integer_mapping(condition_raw.get("relationship"), field_name="when.relationship"),
        always=bool(condition_raw.get("always", False)),
    )
    if not any((condition.intent, condition.engagement, condition.facts, condition.relationship, condition.always)):
        raise ValueError(f"Transição {transition_id!r} não possui condição.")

    return TransitionRule(
        transition_id=transition_id,
        condition=condition,
        next_beat_id=next_beat_id,
        stay=stay,
        priority=int(raw.get("priority", 0) or 0),
        effects=TransitionEffects(
            facts=_string_mapping(effects_raw.get("facts"), field_name="effects.facts"),
            relationship=_integer_mapping(effects_raw.get("relationship"), field_name="effects.relationship"),
        ),
        narrative_effect=NarrativeEffect(
            status=str(narrative_raw.get("status", "") or "").strip(),
            required_outcomes=_string_tuple(narrative_raw.get("required_outcomes"), field_name="narrative_effect.required_outcomes"),
            forbidden_outcomes=_string_tuple(narrative_raw.get("forbidden_outcomes"), field_name="narrative_effect.forbidden_outcomes"),
        ),
        prompt=str(raw.get("prompt", "") or "").strip(),
        fallback=str(raw.get("fallback", "") or "").strip(),
    )


def compile_transition_rules(source: Mapping[str, Any]) -> tuple[TransitionRule, ...]:
    declared = source.get("transitions")
    if declared is not None:
        if not isinstance(declared, list):
            raise ValueError("transitions deve ser uma lista.")
        return tuple(_compile_declared_rule(item, index) for index, item in enumerate(declared))

    legacy_allowed = source.get("allowed_transitions") or {}
    if not isinstance(legacy_allowed, Mapping):
        raise ValueError("allowed_transitions deve ser um mapa.")
    if legacy_allowed:
        return tuple(
            TransitionRule(
                transition_id=f"legacy_{engagement}",
                condition=TransitionCondition(engagement=str(engagement)),
                next_beat_id=str(target),
            )
            for engagement, target in legacy_allowed.items()
            if str(target).strip()
        )

    next_beat_id = str(source.get("next_beat_id", "") or "").strip()
    if next_beat_id:
        return (
            TransitionRule(
                transition_id="legacy_next_beat",
                condition=TransitionCondition(engagement="engaged"),
                next_beat_id=next_beat_id,
            ),
        )
    return ()


def _relationship_matches(requirements: Mapping[str, int], relationship: Mapping[str, int]) -> bool:
    for expression, expected in requirements.items():
        if expression.endswith("_gte"):
            if int(relationship.get(expression[:-4], 0)) < expected:
                return False
        elif expression.endswith("_lte"):
            if int(relationship.get(expression[:-4], 0)) > expected:
                return False
        elif int(relationship.get(expression, 0)) != expected:
            return False
    return True


def _matches(condition: TransitionCondition, *, intent: str, engagement: str, facts: Mapping[str, str], relationship: Mapping[str, int]) -> bool:
    if condition.intent and condition.intent != intent:
        return False
    if condition.engagement and condition.engagement != engagement:
        return False
    if any(str(facts.get(key, "")) != value for key, value in condition.facts.items()):
        return False
    if not _relationship_matches(condition.relationship, relationship):
        return False
    return condition.always or any((condition.intent, condition.engagement, condition.facts, condition.relationship))


def evaluate_transition_rules(
    rules: tuple[TransitionRule, ...],
    *,
    current_beat_id: str,
    intent: str = "",
    engagement: str = "",
    facts: Mapping[str, str] | None = None,
    relationship: Mapping[str, int] | None = None,
) -> TransitionDecision | None:
    indexed = list(enumerate(rules))
    indexed.sort(key=lambda item: (-item[1].priority, item[0]))
    for _, rule in indexed:
        if not _matches(
            rule.condition,
            intent=intent,
            engagement=engagement,
            facts=facts or {},
            relationship=relationship or {},
        ):
            continue
        return TransitionDecision(
            transition_id=rule.transition_id,
            target_beat_id=current_beat_id if rule.stay else rule.next_beat_id,
            stay=rule.stay,
            effects=rule.effects,
            narrative_effect=rule.narrative_effect,
            prompt=rule.prompt,
            fallback=rule.fallback,
        )
    return None
