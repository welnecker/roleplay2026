from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.editorial_beat_context import build_beat_context, render_beat_context
from services.editorial_longitudinal_patterns import (
    render_behavior_patterns,
    update_behavior_patterns,
)
from services.editorial_memory_lifecycle import (
    eligible_memory_ids,
    render_memory_lifecycle_guidance,
    update_memory_lifecycle,
)
from services.editorial_memory_recall import (
    render_memory_recall_guidance,
    select_contextual_memories,
)
from services.editorial_organic_beat_rhythm import (
    build_organic_beat_frame,
    render_organic_beat_frame,
)
from services.editorial_personality_triggers import (
    active_personality_triggers,
    render_personality_triggers,
)
from services.editorial_physical_dramaturgy import (
    render_physical_dramaturgy,
    select_physical_dramaturgy,
)
from services.editorial_psychological_state import (
    apply_card_psychological_deltas,
    render_psychological_state,
)
from services.editorial_resolved_topics import render_resolved_topic_guard
from services.editorial_subjective_impressions import (
    render_subjective_impressions,
    update_subjective_impressions,
)
from services.editorial_user_facts import render_confirmed_user_facts
from services.narrative_context import build_narrative_context, memory_catalog
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_terminal_yard import state_for_target


def _runtime_policy(script: EditorialScript) -> dict[str, Any]:
    direct = script.raw.get("runtime_policy") or {}
    if isinstance(direct, dict) and direct:
        return direct
    legacy = script.raw.get("organic_slack") or {}
    return legacy if isinstance(legacy, dict) else {}


def _strict_canonical_policy(script: EditorialScript) -> dict[str, Any]:
    policy = _runtime_policy(script).get("strict_canonical") or {}
    return policy if isinstance(policy, dict) else {}


def _is_strict_canonical_beat(script: EditorialScript, beat_id: str) -> bool:
    clean = str(beat_id or "").strip()
    policy = _strict_canonical_policy(script)
    beat_ids = {
        str(item).strip()
        for item in policy.get("beat_ids", []) or []
        if str(item).strip()
    }
    prefixes = tuple(
        str(item).strip()
        for item in policy.get("beat_prefixes", []) or []
        if str(item).strip()
    )
    return clean in beat_ids or any(clean.startswith(prefix) for prefix in prefixes)


def _initial_memory_ids(script: EditorialScript) -> list[str]:
    profile = script.raw.get("relationship_memory") or {}
    if not isinstance(profile, dict):
        return []
    return [
        str(item).strip()
        for item in profile.get("initial_memory_ids", []) or []
        if str(item).strip()
    ]


def _memory_ids(script: EditorialScript, state: EditorialState) -> list[str]:
    initial = _initial_memory_ids(script)
    active = [
        item.strip()
        for item in str(state.facts.get("_active_memory_ids", "") or "").split(",")
        if item.strip()
    ]
    return list(dict.fromkeys([*initial, *active]))


def _memory_writes_for_target(script: EditorialScript, target_id: str) -> list[str]:
    source = script.beats.get(target_id) or script.endings.get(target_id) or {}
    return [
        str(item).strip()
        for item in source.get("memory_writes", []) or []
        if str(item).strip()
    ]


def _turn_context(script: EditorialScript, turn: EditorialTurn) -> str:
    source = script.beats.get(turn.target_id) or script.endings.get(turn.target_id) or {}
    parts = [
        turn.system_prompt,
        turn.visible_fallback,
        str(source.get("objective", "") or ""),
        str(source.get("block_id", "") or ""),
        str(source.get("topic_id", "") or ""),
        " ".join(str(item) for item in source.get("allowed_topics", []) or []),
    ]
    return "\n".join(part for part in parts if str(part).strip())


def _mandatory_context_memory_ids(
    script: EditorialScript,
    state: EditorialState,
    active_ids: list[str],
    writes: list[str],
) -> list[str]:
    mandatory: list[str] = []
    if not str(state.facts.get("_memory_recall_turn", "") or "").strip():
        mandatory.extend(_initial_memory_ids(script))
    mandatory.extend(writes)

    catalog = memory_catalog(script.raw)
    mandatory.extend(
        memory_id
        for memory_id in active_ids
        if memory_id in catalog and catalog[memory_id].category == "relationship_origin"
    )
    return list(dict.fromkeys(item for item in mandatory if item))


def _next_lifecycle_sequence(state: EditorialState) -> int:
    try:
        current = int(str(state.facts.get("_memory_lifecycle_sequence", "0") or "0"))
    except (TypeError, ValueError):
        current = 0
    return current + 1


def finalize_editorial_turn(
    script: EditorialScript,
    turn: EditorialTurn,
) -> EditorialTurn:
    """Aplica memória, ciclo de vida, psicologia, ritmo orgânico e continuidade."""

    available_ids = _memory_ids(script, turn.state)
    writes = _memory_writes_for_target(script, turn.target_id)
    updated = EditorialState.from_dict(turn.state.to_dict())
    updated = apply_card_psychological_deltas(script.raw, updated, str(turn.engagement))
    active_ids = list(dict.fromkeys([*available_ids, *writes]))
    updated.facts["_active_memory_ids"] = ",".join(active_ids)
    updated.facts["_pending_memory_writes"] = ",".join(writes)
    updated = state_for_target(script, updated, turn.target_id)

    context_text = _turn_context(script, turn)
    mandatory_ids = _mandatory_context_memory_ids(script, turn.state, active_ids, writes)

    # Todas as memórias conhecidas participam da comparação contextual. O ciclo de
    # vida só as suprime da lembrança espontânea depois dessa comparação, permitindo
    # que uma menção explícita do usuário reative uma memória dormente ou arquivada.
    optional_pool = [memory_id for memory_id in active_ids if memory_id not in mandatory_ids]
    recalled_ids, recalled_facts = select_contextual_memories(
        script.raw,
        optional_pool,
        updated.facts,
        context_text,
    )
    updated.facts = recalled_facts

    lifecycle_sequence = _next_lifecycle_sequence(turn.state)
    updated.facts["_memory_lifecycle_sequence"] = str(lifecycle_sequence)
    lifecycle_fingerprint = (
        f"{lifecycle_sequence}:{turn.target_id}:{turn.engagement}:"
        f"{','.join(writes)}:{','.join(recalled_ids)}"
    )
    updated, lifecycle_states = update_memory_lifecycle(
        script.raw,
        updated,
        active_ids,
        written_ids=writes,
        recalled_ids=recalled_ids,
        fingerprint=lifecycle_fingerprint,
    )
    context_memory_ids = eligible_memory_ids(
        script.raw,
        list(dict.fromkeys([*mandatory_ids, *recalled_ids])),
        updated.facts,
        forced_ids=[*mandatory_ids, *writes, *recalled_ids],
    )
    narrative_context = build_narrative_context(script.raw, context_memory_ids, updated.facts)

    updated, impressions = update_subjective_impressions(
        script.raw,
        updated,
        context_text,
        str(turn.engagement),
    )
    updated.facts["_active_subjective_impression_ids"] = ",".join(
        item.impression_id for item in impressions
    )

    updated, behavior_patterns = update_behavior_patterns(
        script.raw,
        updated,
        context_text,
        str(turn.engagement),
    )

    target = script.beats.get(turn.target_id) or script.endings.get(turn.target_id) or {}
    physical_aspects = select_physical_dramaturgy(
        script.raw,
        updated,
        target,
        context_text,
        str(turn.engagement),
    )

    personality = active_personality_triggers(
        script.raw,
        updated,
        context_text,
        str(turn.engagement),
    )
    updated.facts["_active_personality_trigger_ids"] = ",".join(
        item.trigger_id for item in personality
    )

    runtime_phase = str(updated.facts.get("_runtime_phase", "canonical") or "canonical")
    canonical_member = _is_strict_canonical_beat(script, turn.target_id)
    inject_canonical_prompt = runtime_phase == "canonical" and canonical_member
    strict_policy = _strict_canonical_policy(script)
    state_fact = str(strict_policy.get("state_fact", "") or "").strip()
    updated.facts["_force_fixed_response"] = "false"
    if state_fact:
        updated.facts[state_fact] = "true" if canonical_member else "false"

    prepared_turn = replace(turn, state=updated)
    beat_context = build_beat_context(script, turn.state, prepared_turn)
    beat_frame = build_organic_beat_frame(script.raw, target, beat_context, updated)
    psychological_context = render_psychological_state(script.raw, updated)
    impressions_context = render_subjective_impressions(impressions)
    patterns_context = render_behavior_patterns(behavior_patterns)
    physical_context = render_physical_dramaturgy(physical_aspects)
    personality_context = render_personality_triggers(personality)
    user_facts_context = render_confirmed_user_facts(updated.facts)
    recall_guidance = render_memory_recall_guidance(recalled_ids)
    lifecycle_guidance = render_memory_lifecycle_guidance(lifecycle_states)
    resolved_guard = render_resolved_topic_guard(script, updated)
    prompt_parts = [
        render_organic_beat_frame(beat_frame),
        render_beat_context(beat_context),
        narrative_context,
        psychological_context,
        impressions_context,
        patterns_context,
        physical_context,
        personality_context,
        user_facts_context,
        recall_guidance,
        lifecycle_guidance,
        turn.system_prompt,
        resolved_guard,
    ]
    prompt = "\n\n".join(part.strip() for part in prompt_parts if part.strip())

    if inject_canonical_prompt:
        title = str(strict_policy.get("prompt_title", "") or "").strip()
        title = title or "CONTINUIDADE CANÔNICA ESTRITA"
        prompt = (
            f"{prompt}\n\n{title}:\n"
            "- Responda primeiro ao conteúdo específico do usuário em uma ou duas frases curtas e naturais.\n"
            "- Em seguida, entregue a linha canônica do movimento atual, preservando integralmente seu sentido e sua ação.\n"
            "- A reação e a linha canônica devem formar uma única fala contínua.\n"
            "- Não antecipe ações, mudanças de cena, encerramentos ou acontecimentos de beats posteriores.\n"
            "- Não acrescente nada depois da linha canônica.\n"
            "- Não abra uma nova pergunta além da que já existir na própria linha canônica.\n"
            "- Qualquer pensamento interno de Mary deve estar em primeira pessoa e servir à forma da fala, nunca aparecer como narração psicológica em terceira pessoa."
        )

    return replace(prepared_turn, system_prompt=prompt.strip())


__all__ = ["finalize_editorial_turn"]
