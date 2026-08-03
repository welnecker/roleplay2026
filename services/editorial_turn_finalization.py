from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.narrative_context import build_narrative_context
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


def _organic_policy(script: EditorialScript) -> dict[str, Any]:
    policy = script.raw.get("organic_slack") or {}
    return policy if isinstance(policy, dict) else {}


def _strict_canonical_policy(script: EditorialScript) -> dict[str, Any]:
    policy = _organic_policy(script).get("strict_canonical") or {}
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


def _memory_ids(state: EditorialState) -> list[str]:
    return [
        item.strip()
        for item in str(state.facts.get("_active_memory_ids", "") or "").split(",")
        if item.strip()
    ]


def _memory_writes_for_target(script: EditorialScript, target_id: str) -> list[str]:
    source = script.beats.get(target_id) or script.endings.get(target_id) or {}
    return [
        str(item).strip()
        for item in source.get("memory_writes", []) or []
        if str(item).strip()
    ]


def finalize_editorial_turn(
    script: EditorialScript,
    turn: EditorialTurn,
) -> EditorialTurn:
    """Aplica memória narrativa e continuidade canônica ao turno decidido."""

    previous_ids = _memory_ids(turn.state)
    context = build_narrative_context(script.raw, previous_ids, turn.state.facts)
    writes = _memory_writes_for_target(script, turn.target_id)
    updated = EditorialState.from_dict(turn.state.to_dict())
    updated.facts["_active_memory_ids"] = ",".join(
        dict.fromkeys([*previous_ids, *writes])
    )
    updated.facts["_pending_memory_writes"] = ",".join(writes)

    strict = _is_strict_canonical_beat(script, turn.target_id)
    strict_policy = _strict_canonical_policy(script)
    state_fact = str(strict_policy.get("state_fact", "") or "").strip()
    updated.facts["_force_fixed_response"] = "false"
    if state_fact:
        updated.facts[state_fact] = "true" if strict else "false"

    prompt = turn.system_prompt
    if strict:
        title = str(strict_policy.get("prompt_title", "") or "").strip()
        title = title or "CONTINUIDADE CANÔNICA ESTRITA"
        prompt = (
            f"{prompt}\n\n{title}:\n"
            "- Responda primeiro ao conteúdo específico do usuário em uma ou duas frases curtas e naturais.\n"
            "- Em seguida, entregue a linha canônica do movimento atual, preservando integralmente seu sentido e sua ação.\n"
            "- A reação e a linha canônica devem formar uma única fala contínua.\n"
            "- Não antecipe ações, mudanças de cena, encerramentos ou acontecimentos de beats posteriores.\n"
            "- Não acrescente nada depois da linha canônica.\n"
            "- Não abra uma nova pergunta além da que já existir na própria linha canônica."
        )

    return replace(
        turn,
        state=updated,
        system_prompt=f"{context}\n\n{prompt}".strip(),
    )


__all__ = ["finalize_editorial_turn"]
