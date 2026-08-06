from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Mapping


_HISTORY_KEY = "_behavior_pattern_history_json"
_PATTERN_TURN_KEY = "_behavior_pattern_turn"
_ACTIVE_KEY = "_active_behavior_pattern_ids"


@dataclass(frozen=True, slots=True)
class ActiveBehaviorPattern:
    pattern_id: str
    label: str
    interpretation: str
    confidence: float
    observations: int


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("behavior_patterns") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("behavior_patterns") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _normalized_pattern(pattern: str) -> str:
    return str(pattern).replace("\\\\", "\\")


def _matches(text: str, patterns: Any) -> bool:
    declared = _items(patterns)
    if not declared:
        return False
    for pattern in declared:
        try:
            if re.search(_normalized_pattern(pattern), text, flags=re.IGNORECASE):
                return True
        except re.error as exc:
            raise ValueError(f"Regex inválida em behavior_patterns: {exc}") from exc
    return False


def _load_history(facts: Mapping[str, str]) -> list[dict[str, Any]]:
    raw = str(facts.get(_HISTORY_KEY, "") or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [dict(item) for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _observation(policy: Mapping[str, Any], context_text: str, engagement: str) -> dict[str, Any]:
    signals: list[str] = []
    definitions = policy.get("signals") or {}
    if isinstance(definitions, dict):
        for signal_id, raw in definitions.items():
            if not isinstance(raw, dict):
                continue
            engagements = set(_items(raw.get("engagements")))
            engagement_match = bool(engagements and str(engagement) in engagements)
            pattern_match = _matches(context_text, raw.get("context_patterns"))
            mode = str(raw.get("match", "any") or "any").strip()
            matched = (
                engagement_match and pattern_match
                if mode == "all" and engagements and _items(raw.get("context_patterns"))
                else engagement_match or pattern_match
            )
            if matched:
                signals.append(str(signal_id))
    return {"engagement": str(engagement), "signals": sorted(set(signals))}


def _count_signal(history: list[dict[str, Any]], signal_id: str) -> int:
    return sum(signal_id in set(_items(item.get("signals"))) for item in history)


def _count_engagement(history: list[dict[str, Any]], engagements: set[str]) -> int:
    return sum(str(item.get("engagement", "")) in engagements for item in history)


def _switches(history: list[dict[str, Any]], positive: set[str], negative: set[str]) -> int:
    groups: list[str] = []
    for item in history:
        engagement = str(item.get("engagement", ""))
        signals = set(_items(item.get("signals")))
        if engagement in positive or signals.intersection(positive):
            groups.append("positive")
        elif engagement in negative or signals.intersection(negative):
            groups.append("negative")
    return sum(left != right for left, right in zip(groups, groups[1:]))


def _pattern_matches(definition: Mapping[str, Any], history: list[dict[str, Any]]) -> tuple[bool, int]:
    window_size = max(1, int(definition.get("window", len(history) or 1) or 1))
    window = history[-window_size:]
    minimum_observations = max(1, int(definition.get("min_observations", 2) or 2))
    if len(window) < minimum_observations:
        return False, len(window)

    kind = str(definition.get("kind", "signal_count") or "signal_count").strip()
    if kind == "signal_count":
        signal_id = str(definition.get("signal", "") or "").strip()
        required = max(1, int(definition.get("min_count", minimum_observations) or minimum_observations))
        count = _count_signal(window, signal_id)
        return count >= required, count
    if kind == "engagement_count":
        engagements = set(_items(definition.get("engagements")))
        required = max(1, int(definition.get("min_count", minimum_observations) or minimum_observations))
        count = _count_engagement(window, engagements)
        return count >= required, count
    if kind == "alternation":
        positive = set(_items(definition.get("positive")))
        negative = set(_items(definition.get("negative")))
        required = max(1, int(definition.get("min_switches", 2) or 2))
        count = _switches(window, positive, negative)
        return count >= required, count + 1
    raise ValueError(f"Tipo desconhecido em behavior_patterns: {kind!r}")


def update_behavior_patterns(
    document: Mapping[str, Any],
    state: Any,
    context_text: str,
    engagement: str,
) -> tuple[Any, list[ActiveBehaviorPattern]]:
    """Lê padrões em múltiplos turnos sem transformar repetição em diagnóstico."""

    policy = _policy(document)
    definitions = policy.get("patterns") or {}
    if not isinstance(definitions, dict):
        state.facts[_ACTIVE_KEY] = ""
        return state, []

    history = _load_history(state.facts)
    fingerprint = f"{state.node_id}:{len(state.recent_engagement)}:{engagement}"
    if str(state.facts.get(_PATTERN_TURN_KEY, "") or "") != fingerprint:
        history.append(_observation(policy, context_text, engagement))
        maximum_history = max(2, int(policy.get("history_size", 8) or 8))
        history = history[-maximum_history:]
        state.facts[_HISTORY_KEY] = json.dumps(history, ensure_ascii=False, sort_keys=True)
        state.facts[_PATTERN_TURN_KEY] = fingerprint

    active: list[ActiveBehaviorPattern] = []
    for pattern_id, raw in definitions.items():
        if not isinstance(raw, dict):
            continue
        matched, observations = _pattern_matches(raw, history)
        if not matched:
            continue
        interpretation = str(raw.get("interpretation", "") or "").strip()
        if not interpretation:
            continue
        minimum = max(1, int(raw.get("min_observations", 2) or 2))
        confidence = min(0.9, float(policy.get("base_confidence", 0.4) or 0.4) + max(0, observations - minimum) * 0.1)
        active.append(
            ActiveBehaviorPattern(
                pattern_id=str(pattern_id),
                label=str(raw.get("label", pattern_id) or pattern_id),
                interpretation=interpretation,
                confidence=confidence,
                observations=observations,
            )
        )

    active.sort(key=lambda item: (-item.confidence, -item.observations, item.pattern_id))
    maximum = max(0, int(policy.get("max_visible_patterns", 2) or 2))
    selected = active[:maximum] if maximum else []
    state.facts[_ACTIVE_KEY] = ",".join(item.pattern_id for item in selected)
    return state, selected


def render_behavior_patterns(patterns: list[ActiveBehaviorPattern]) -> str:
    if not patterns:
        return ""
    lines = ["PADRÕES PERCEBIDOS AO LONGO DA INTERAÇÃO:"]
    lines.extend(f"- {item.label}: {item.interpretation}" for item in patterns)
    lines.extend(
        (
            "REGRAS DE LEITURA LONGITUDINAL:",
            "- Trate estes padrões como tendências provisórias observadas em vários turnos, nunca como essência fixa do usuário.",
            "- Faça a leitura afetar expectativa, cautela e iniciativa, sem recitar um histórico ou acusar o usuário.",
            "- Um comportamento novo pode enfraquecer ou encerrar um padrão anteriormente percebido.",
            "- Não mencione janelas, contagens, sinais, IDs, pontuações ou regras internas.",
            "- Fatos explícitos e o comportamento do turno atual prevalecem sobre tendências anteriores.",
        )
    )
    return "\n".join(lines)


__all__ = [
    "ActiveBehaviorPattern",
    "render_behavior_patterns",
    "update_behavior_patterns",
]
