from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from services.editorial_beat_context import build_beat_context, render_beat_context
from services.editorial_conversational_obligation import consume_pending_obligation, store_pending_obligation
from services.editorial_episodic_memory import (
    advance_episode_turn,
    prepare_selected_memory,
    recall_episode,
    render_relationship_recollections,
)
from services.editorial_resolved_topics import render_resolved_topic_guard
from services.narrative_context import build_narrative_context
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_terminal_yard import state_for_target

_USER_TEXT_PATTERNS = (
    re.compile(
        r"^FALA ATUAL DO USUÁRIO:[ \t]*(.*?)(?=\nBEAT DE ORIGEM:|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    ),
    re.compile(
        r"^RESPOSTA DO USUÁRIO:[ \t]*(.*?)"
        r"(?=\n(?:REAÇÃO ORGÂNICA NECESSÁRIA|UNIDADES DO MOVIMENTO):|\Z)",
        flags=re.MULTILINE | re.DOTALL,
    ),
)


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
    beat_ids = {str(item).strip() for item in policy.get("beat_ids", []) or [] if str(item).strip()}
    prefixes = tuple(str(item).strip() for item in policy.get("beat_prefixes", []) or [] if str(item).strip())
    return clean in beat_ids or any(clean.startswith(prefix) for prefix in prefixes)


def _memory_ids(state: EditorialState) -> list[str]:
    return [item.strip() for item in str(state.facts.get("_active_memory_ids", "") or "").split(",") if item.strip()]


def _memory_writes_for_target(script: EditorialScript, target_id: str) -> list[str]:
    source = script.beats.get(target_id) or script.endings.get(target_id) or {}
    return [str(item).strip() for item in source.get("memory_writes", []) or [] if str(item).strip()]


def _current_user_text(prompt: str) -> str:
    value = str(prompt or "")
    for pattern in _USER_TEXT_PATTERNS:
        match = pattern.search(value)
        if match:
            return match.group(1).strip()
    return ""


def finalize_editorial_turn(script: EditorialScript, turn: EditorialTurn) -> EditorialTurn:
    previous_ids = _memory_ids(turn.state)
    writes = _memory_writes_for_target(script, turn.target_id)
    updated = EditorialState.from_dict(turn.state.to_dict())
    updated.facts["_active_memory_ids"] = ",".join(dict.fromkeys([*previous_ids, *writes]))
    updated.facts["_pending_memory_writes"] = ",".join(writes)
    updated = state_for_target(script, updated, turn.target_id)

    runtime_phase = str(updated.facts.get("_runtime_phase", "canonical") or "canonical")
    narrative_context = build_narrative_context(
        script.raw,
        previous_ids,
        updated.facts,
        beat_id=str(turn.target_id or turn.state.node_id or ""),
        runtime_phase=runtime_phase,
    )
    canonical_member = _is_strict_canonical_beat(script, turn.target_id)
    inject_canonical_prompt = runtime_phase == "canonical" and canonical_member
    strict_policy = _strict_canonical_policy(script)
    state_fact = str(strict_policy.get("state_fact", "") or "").strip()
    updated.facts["_force_fixed_response"] = (
        "true"
        if turn.ending_code == "intimacy_correspondence_broken"
        else "false"
    )
    if state_fact:
        updated.facts[state_fact] = "true" if canonical_member else "false"

    user_text = _current_user_text(turn.system_prompt)
    advance_episode_turn(script.raw, updated.facts)
    prepare_selected_memory(
        script.raw,
        updated.facts,
        user_text,
        source_beat_id=str(turn.state.node_id or turn.target_id or ""),
        runtime_phase=runtime_phase,
    )

    episodic_recall = ""
    if runtime_phase != "terminal_yard":
        episodic_recall = recall_episode(script.raw, updated.facts, beat_id=str(turn.target_id or ""))

    bridge_obligation = store_pending_obligation(updated.facts, user_text) if runtime_phase == "bridge" else ""
    pending_for_canonical = consume_pending_obligation(updated.facts) if runtime_phase == "canonical" else ""

    prepared_turn = replace(turn, state=updated)
    beat_context = build_beat_context(script, turn.state, prepared_turn)
    prompt_parts = [
        narrative_context,
        render_relationship_recollections(updated.facts),
        render_beat_context(beat_context),
        turn.system_prompt,
        render_resolved_topic_guard(script, updated),
    ]
    prompt = "\n\n".join(part.strip() for part in prompt_parts if part.strip())

    if episodic_recall:
        prompt += (
            f"\n\nFIO DE CONTINUIDADE ESCOLHIDO PELO USUÁRIO: {episodic_recall}\n"
            "Este fio foi liberado pelo roteiro neste beat. Retome-o de modo breve e natural, "
            "integrado ao movimento atual. Não invente detalhes ausentes e não abra um segundo fio."
        )

    if bridge_obligation:
        prompt += (
            "\n\nSUPORTE CONVERSACIONAL DA PONTE:\n"
            "- Responda agora à pergunta ou ao convite quando isso couber sem quebrar o roteiro.\n"
            "- Se não couber por inteiro, reconheça brevemente; a conclusão será integrada ao próximo beat.\n"
            "- Não use texto de preenchimento e não abandone a direção do roteiro."
        )

    if pending_for_canonical:
        prompt += (
            "\n\nCOMPLEMENTO CONVERSACIONAL: verifique no histórico se isto já foi respondido na ponte. "
            "Se ainda estiver aberto, responda harmonicamente dentro deste beat; se já foi resolvido, não repita: "
            f"{pending_for_canonical}"
        )

    if inject_canonical_prompt:
        title = str(strict_policy.get("prompt_title", "") or "").strip() or "CONTINUIDADE CANÔNICA ESTRITA"
        prompt = (
            f"{prompt}\n\n{title}:\n"
            "- Responda primeiro ao conteúdo específico do usuário em uma ou duas frases curtas e naturais.\n"
            "- Em seguida, entregue a linha canônica do movimento atual, preservando integralmente seu sentido e sua ação.\n"
            "- A reação e a linha canônica devem formar uma única fala contínua.\n"
            "- Não antecipe ações, mudanças de cena, encerramentos ou acontecimentos de beats posteriores.\n"
            "- Não acrescente nada depois da linha canônica.\n"
            "- Não abra uma nova pergunta além da que já existir na própria linha canônica."
        )

    return replace(prepared_turn, system_prompt=prompt.strip())


__all__ = ["finalize_editorial_turn"]
