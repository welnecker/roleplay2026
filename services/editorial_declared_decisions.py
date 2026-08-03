from __future__ import annotations

import re
from typing import Any, Callable

from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


DecisionFunction = Callable[[EditorialScript, EditorialState, str], EditorialTurn]
ClassifierFunction = Callable[[str], str]


class _SafeFormat(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _character_name(script: EditorialScript) -> str:
    character = script.raw.get("character") or {}
    if isinstance(character, dict):
        name = str(character.get("name", "") or "").strip()
        if name:
            return name
    return "A personagem"


def _special_decisions(script: EditorialScript) -> list[dict[str, Any]]:
    organic = script.raw.get("organic_slack") or {}
    if not isinstance(organic, dict):
        return []
    rules = organic.get("special_decisions") or []
    if not isinstance(rules, list):
        raise ValueError("organic_slack.special_decisions deve ser uma lista.")
    return [item for item in rules if isinstance(item, dict)]


def _rule_for_beat(script: EditorialScript, beat_id: str) -> dict[str, Any] | None:
    clean = str(beat_id or "").strip()
    for rule in _special_decisions(script):
        if str(rule.get("beat_id", "") or "").strip() == clean:
            return rule
    return None


def _matches_patterns(value: str, patterns: Any) -> bool:
    if not isinstance(patterns, list):
        return False
    return any(
        re.search(str(pattern), value, flags=re.IGNORECASE) is not None
        for pattern in patterns
        if str(pattern).strip()
    )


def _classify_declared_intent(rule: dict[str, Any], user_text: str) -> str:
    value = " ".join(str(user_text or "").casefold().split())
    classifiers = rule.get("classifiers") or []
    if not isinstance(classifiers, list):
        raise ValueError("special_decisions.classifiers deve ser uma lista.")

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
            return intent
        if _matches_patterns(value, classifier.get("patterns")):
            return intent
    return default_intent


def _dialogue_anchor(script: EditorialScript, beat_id: str) -> str:
    source = script.beats.get(beat_id) or script.endings.get(beat_id) or {}
    for unit in source.get("units", []) or []:
        if isinstance(unit, dict) and unit.get("kind") == "dialogue":
            return str(unit.get("anchor") or unit.get("text") or "")
    visible = source.get("visible_delivery") or {}
    return str(visible.get("text", "") if isinstance(visible, dict) else "")


def _render(value: Any, variables: dict[str, str]) -> str:
    return str(value or "").format_map(_SafeFormat(variables)).strip()


def _declared_facts(outcome: dict[str, Any], variables: dict[str, str]) -> dict[str, str]:
    facts = outcome.get("facts") or {}
    if not isinstance(facts, dict):
        raise ValueError("special_decisions.outcomes.*.facts deve ser um mapa.")
    return {str(key): _render(value, variables) for key, value in facts.items()}


def decide_declared_special_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    base_decide: DecisionFunction,
    classify_message: ClassifierFunction,
) -> EditorialTurn | None:
    """Executa uma decisão especial inteiramente descrita pelo documento editorial."""

    current_id = state.node_id or script.first_beat_id
    rule = _rule_for_beat(script, current_id)
    if rule is None:
        return None

    intent = _classify_declared_intent(rule, user_text)
    outcomes = rule.get("outcomes") or {}
    if not isinstance(outcomes, dict):
        raise ValueError("special_decisions.outcomes deve ser um mapa.")
    outcome = outcomes.get(intent) or outcomes.get("default")
    if not isinstance(outcome, dict):
        raise ValueError(
            f"Decisão especial sem resultado para {current_id!r} / {intent!r}."
        )

    variables = {
        "intent": intent,
        "user_text": str(user_text or ""),
        "character_name": _character_name(script),
        "current_beat_id": current_id,
    }
    mode = str(outcome.get("mode", "repeat") or "repeat").strip()

    if mode == "advance":
        turn = base_decide(script, state, user_text)
        updated = EditorialState.from_dict(turn.state.to_dict())
        updated.facts.update(_declared_facts(outcome, variables))
        return EditorialTurn(
            engagement=turn.engagement,
            target_id=turn.target_id,
            visible_fallback=turn.visible_fallback,
            system_prompt=turn.system_prompt,
            state=updated,
        )

    if mode not in {"repeat", "redirect"}:
        raise ValueError(f"Modo de decisão especial desconhecido: {mode!r}")

    target_id = current_id
    if mode == "redirect":
        target_id = str(outcome.get("target_id", "") or "").strip()
        if not target_id or target_id not in script.beats:
            raise ValueError(f"Destino especial inexistente: {target_id!r}")

    updated = EditorialState.from_dict(state.to_dict())
    updated.node_id = target_id
    updated.finished = False
    updated.run_status = "active"
    updated.ending_code = ""
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    updated.facts.update(_declared_facts(outcome, variables))

    fallback = _render(outcome.get("fallback"), variables) or _dialogue_anchor(
        script, target_id
    )
    prompt = _render(outcome.get("prompt"), variables)
    return EditorialTurn(
        engagement=classify_message(user_text),  # type: ignore[arg-type]
        target_id=target_id,
        visible_fallback=fallback,
        system_prompt=prompt,
        state=updated,
    )
