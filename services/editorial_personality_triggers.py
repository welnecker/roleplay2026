from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ActivePersonalityTrigger:
    trigger_id: str
    priority: int
    effect: str
    visible_signals: tuple[str, ...]
    avoid: tuple[str, ...]


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("personality_triggers") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("personality_triggers") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _normalized_pattern(pattern: str) -> str:
    """Aceita regex declarada diretamente em Python ou serializada por YAML/JSON.

    Alguns produtores entregam ``\\b`` já desserializado como dois caracteres de
    barra antes de ``b``. Nesse caso, normalizamos apenas barras duplicadas, sem
    aplicar ``unicode_escape`` ao texto inteiro e sem corromper acentos.
    """

    return str(pattern).replace("\\\\", "\\")


def _matches_text(text: str, patterns: Any) -> bool:
    for declared_pattern in _items(patterns):
        pattern = _normalized_pattern(declared_pattern)
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        except re.error as exc:
            raise ValueError(f"Regex inválida em personality_triggers: {exc}") from exc
    return False


def _matches_dimensions(state: Any, conditions: Mapping[str, Any]) -> bool:
    for dimension_id, raw in conditions.items():
        if not hasattr(state, str(dimension_id)) or not isinstance(raw, dict):
            return False
        value = int(getattr(state, str(dimension_id)))
        minimum = int(raw.get("min", 0) or 0)
        maximum = int(raw.get("max", 10) or 10)
        if not minimum <= value <= maximum:
            return False
    return True


def active_personality_triggers(
    document: Mapping[str, Any],
    state: Any,
    context_text: str,
    engagement: str,
) -> list[ActivePersonalityTrigger]:
    policy = _policy(document)
    definitions = policy.get("triggers") or {}
    if not isinstance(definitions, dict):
        return []

    selected: list[ActivePersonalityTrigger] = []
    for trigger_id, raw in definitions.items():
        if not isinstance(raw, dict):
            continue
        when = raw.get("when") or {}
        if not isinstance(when, dict):
            continue
        engagements = set(_items(when.get("engagements")))
        if engagements and str(engagement) not in engagements:
            continue
        dimensions = when.get("dimensions") or {}
        if dimensions and (not isinstance(dimensions, dict) or not _matches_dimensions(state, dimensions)):
            continue
        patterns = when.get("context_patterns") or []
        if patterns and not _matches_text(context_text, patterns):
            continue
        required_facts = when.get("facts") or {}
        if isinstance(required_facts, dict):
            if any(str(state.facts.get(str(key), "")) != str(value) for key, value in required_facts.items()):
                continue
        effect = str(raw.get("effect", "") or "").strip()
        if not effect:
            continue
        selected.append(
            ActivePersonalityTrigger(
                trigger_id=str(trigger_id),
                priority=int(raw.get("priority", 5) or 5),
                effect=effect,
                visible_signals=_items(raw.get("visible_signals")),
                avoid=_items(raw.get("avoid")),
            )
        )

    selected.sort(key=lambda item: (-item.priority, item.trigger_id))
    maximum = max(0, int(policy.get("max_active_triggers", 2) or 2))
    return selected[:maximum] if maximum else []


def render_personality_triggers(triggers: list[ActivePersonalityTrigger]) -> str:
    if not triggers:
        return ""
    lines = ["PERSONALIDADE ATIVADA PELO CONTEXTO:"]
    for trigger in triggers:
        lines.append(f"- {trigger.effect}")
        lines.extend(f"  Sinal visível: {item}" for item in trigger.visible_signals)
        lines.extend(f"  Evite: {item}" for item in trigger.avoid)
    lines.extend(
        (
            "REGRAS:",
            "- Expresse os gatilhos na escolha de palavras, ritmo, iniciativa e grau de exposição.",
            "- Não mencione gatilhos, traços, diagnósticos ou regras internas ao usuário.",
            "- O gatilho modula a personalidade; não altera fatos, limites, consentimento ou continuidade canônica.",
        )
    )
    return "\n".join(lines)


__all__ = ["ActivePersonalityTrigger", "active_personality_triggers", "render_personality_triggers"]
