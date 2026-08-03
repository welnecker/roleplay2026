from __future__ import annotations

from typing import Any

from services.editorial_runtime_types import EditorialScript, EditorialState
from services.organic_interaction import extract_user_facts


def normal_editorial_target(
    script: EditorialScript,
    state: EditorialState,
    engagement: str,
) -> str:
    current_id = state.node_id or script.first_beat_id
    beat = script.beats.get(current_id) or {}
    transitions = beat.get("on_user") or {}
    return str(
        transitions.get(engagement)
        or transitions.get("engaged")
        or beat.get("terminal_transition")
        or ""
    )


def state_with_extracted_facts(
    state: EditorialState,
    user_text: str,
) -> EditorialState:
    updated = EditorialState.from_dict(state.to_dict())
    updated.facts = extract_user_facts(user_text, updated.facts)
    return updated


def _skip_target_for_beat(beat: dict[str, Any], facts: dict[str, str]) -> str:
    rules = beat.get("skip_when_facts") or {}
    if not isinstance(rules, dict):
        raise ValueError("skip_when_facts deve ser um mapa de fato para beat de destino.")
    for fact_name, configured_target in rules.items():
        if str(facts.get(str(fact_name), "") or "").strip():
            return str(configured_target or "").strip()
    return ""


def resolve_declared_editorial_target(
    script: EditorialScript,
    initial_target: str,
    facts: dict[str, str],
) -> tuple[str, tuple[str, ...]]:
    target = str(initial_target or "").strip()
    skipped: list[str] = []
    visited: set[str] = set()

    while target:
        if target in visited:
            chain = " -> ".join([*skipped, target])
            raise ValueError(f"Ciclo em skip_when_facts: {chain}")
        visited.add(target)

        beat = script.beats.get(target)
        if beat is None:
            if target in script.endings:
                break
            raise ValueError(f"skip_when_facts aponta para alvo inexistente: {target!r}")

        next_target = _skip_target_for_beat(beat, facts)
        if not next_target:
            break
        skipped.append(target)
        target = next_target

    return target, tuple(skipped)


def routing_state_for_declared_skips(
    script: EditorialScript,
    state: EditorialState,
    engagement: str,
    *,
    original_facts: dict[str, str],
) -> EditorialState:
    initial_target = state.pending_next_beat_id or normal_editorial_target(
        script, state, engagement
    )
    final_target, skipped = resolve_declared_editorial_target(
        script, initial_target, state.facts
    )
    if not skipped:
        return state

    routed = EditorialState.from_dict(state.to_dict())
    routed.pending_next_beat_id = final_target
    routed.facts["_declared_skip_applied"] = ",".join(skipped)

    for fact_name, value in list(routed.facts.items()):
        if fact_name.startswith("_") or original_facts.get(fact_name) == value:
            continue
        routed.facts[f"_acknowledged_{fact_name}"] = value
    return routed


__all__ = [
    "normal_editorial_target",
    "resolve_declared_editorial_target",
    "routing_state_for_declared_skips",
    "state_with_extracted_facts",
]
