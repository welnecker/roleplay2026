from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping


_CONTEXT_SCALAR_FIELDS = (
    "relationship_stage",
    "setting",
    "privacy",
    "intimacy_level",
    "mary_disclosed_desire",
    "mutual_attraction_confirmed",
)
_CONTEXT_LIST_FIELDS = (
    "allowed_interactions",
    "recoverable_tensions",
    "terminal_violations",
    "immediate_endings",
)


@dataclass(frozen=True, slots=True)
class ResolvedInteractionContext:
    relationship_stage: str = "unspecified"
    setting: str = "unspecified"
    privacy: str = "unspecified"
    intimacy_level: int = 0
    mary_disclosed_desire: bool = False
    mutual_attraction_confirmed: bool = False
    allowed_interactions: tuple[str, ...] = ()
    recoverable_tensions: tuple[str, ...] = ()
    terminal_violations: tuple[str, ...] = ()
    immediate_endings: tuple[str, ...] = ()
    applied_progressions: tuple[str, ...] = ()


def _as_mapping(value: Any, *, field: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} deve ser um mapa")
    return {str(key): deepcopy(item) for key, item in value.items()}


def _strings(value: Any, *, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field} deve ser texto ou lista")
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _bool(value: Any, *, field: str) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"true", "1", "yes", "sim"}:
        return True
    if text in {"false", "0", "no", "não", "nao", ""}:
        return False
    raise ValueError(f"{field} deve ser booleano")


def merge_interaction_context(*levels: Any) -> dict[str, Any]:
    """Combina card, bloco e beat sem inferir progressão narrativa."""

    merged: dict[str, Any] = {}
    progression: list[dict[str, Any]] = []
    for index, value in enumerate(levels):
        current = _as_mapping(value, field=f"interaction_context[{index}]")
        for field in _CONTEXT_SCALAR_FIELDS:
            if field in current:
                merged[field] = deepcopy(current[field])
        for field in _CONTEXT_LIST_FIELDS:
            if field in current:
                merged[field] = _strings(current[field], field=field)
        rules = current.get("progression")
        if rules is not None:
            if not isinstance(rules, list):
                raise ValueError("interaction_context.progression deve ser uma lista")
            progression.extend(deepcopy(item) for item in rules if isinstance(item, Mapping))
    if progression:
        merged["progression"] = progression
    return merged


def validate_interaction_context(value: Any, *, location: str = "interaction_context") -> None:
    context = _as_mapping(value, field=location)
    if not context:
        return
    if "intimacy_level" in context:
        level = int(context.get("intimacy_level", 0) or 0)
        if level < 0 or level > 5:
            raise ValueError(f"{location}.intimacy_level deve estar entre 0 e 5")
    for field in ("mary_disclosed_desire", "mutual_attraction_confirmed"):
        if field in context:
            _bool(context[field], field=f"{location}.{field}")
    for field in _CONTEXT_LIST_FIELDS:
        if field in context:
            _strings(context[field], field=f"{location}.{field}")
    progression = context.get("progression") or []
    if not isinstance(progression, list):
        raise ValueError(f"{location}.progression deve ser uma lista")
    for index, rule in enumerate(progression):
        if not isinstance(rule, Mapping):
            raise ValueError(f"{location}.progression[{index}] deve ser um mapa")
        when_facts = rule.get("when_facts") or {}
        changes = rule.get("set") or {}
        if not isinstance(when_facts, Mapping) or not when_facts:
            raise ValueError(f"{location}.progression[{index}].when_facts deve declarar fatos")
        if not isinstance(changes, Mapping) or not changes:
            raise ValueError(f"{location}.progression[{index}].set deve declarar alterações")
        unknown = set(changes) - set(_CONTEXT_SCALAR_FIELDS) - set(_CONTEXT_LIST_FIELDS)
        if unknown:
            raise ValueError(
                f"{location}.progression[{index}].set possui campos desconhecidos: {sorted(unknown)}"
            )


def _facts_match(expected: Mapping[str, Any], facts: Mapping[str, str]) -> bool:
    for key, expected_value in expected.items():
        actual = str(facts.get(str(key), "") or "").strip().casefold()
        wanted = str(expected_value or "").strip().casefold()
        if actual != wanted:
            return False
    return True


def resolve_interaction_context(
    compiled_context: Any,
    facts: Mapping[str, str] | None = None,
) -> ResolvedInteractionContext:
    """Resolve somente progressões declaradas e sustentadas por fatos da run."""

    context = merge_interaction_context(compiled_context)
    validate_interaction_context(context)
    resolved = deepcopy(context)
    applied: list[str] = []
    state_facts = {str(key): str(value) for key, value in dict(facts or {}).items()}
    for index, rule in enumerate(context.get("progression", []) or []):
        when_facts = dict(rule.get("when_facts") or {})
        if not _facts_match(when_facts, state_facts):
            continue
        changes = dict(rule.get("set") or {})
        for field in _CONTEXT_SCALAR_FIELDS:
            if field in changes:
                resolved[field] = deepcopy(changes[field])
        for field in _CONTEXT_LIST_FIELDS:
            if field in changes:
                resolved[field] = _strings(changes[field], field=field)
        applied.append(str(rule.get("id") or f"progression_{index + 1}"))

    return ResolvedInteractionContext(
        relationship_stage=str(resolved.get("relationship_stage", "unspecified") or "unspecified"),
        setting=str(resolved.get("setting", "unspecified") or "unspecified"),
        privacy=str(resolved.get("privacy", "unspecified") or "unspecified"),
        intimacy_level=max(0, min(5, int(resolved.get("intimacy_level", 0) or 0))),
        mary_disclosed_desire=_bool(
            resolved.get("mary_disclosed_desire", False), field="mary_disclosed_desire"
        ),
        mutual_attraction_confirmed=_bool(
            resolved.get("mutual_attraction_confirmed", False),
            field="mutual_attraction_confirmed",
        ),
        allowed_interactions=tuple(_strings(resolved.get("allowed_interactions"), field="allowed_interactions")),
        recoverable_tensions=tuple(_strings(resolved.get("recoverable_tensions"), field="recoverable_tensions")),
        terminal_violations=tuple(_strings(resolved.get("terminal_violations"), field="terminal_violations")),
        immediate_endings=tuple(_strings(resolved.get("immediate_endings"), field="immediate_endings")),
        applied_progressions=tuple(applied),
    )


__all__ = [
    "ResolvedInteractionContext",
    "merge_interaction_context",
    "resolve_interaction_context",
    "validate_interaction_context",
]
