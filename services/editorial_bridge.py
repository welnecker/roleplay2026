from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn

_PHASE_KEY = "_runtime_phase"
_BRIDGE_ORIGIN_KEY = "_bridge_origin_beat_id"
_BRIDGE_TARGET_KEY = "_bridge_target_beat_id"
_BRIDGE_TURNS_KEY = "_bridge_turn_count"


def bridge_policy(script: EditorialScript) -> dict[str, Any]:
    raw = script.raw.get("bridge_policy") or {}
    return raw if isinstance(raw, dict) else {}


def bridge_enabled_for_beat(script: EditorialScript, beat_id: str) -> bool:
    """Ativa a ponte somente onde o card declarou a nova máquina de estados."""

    policy = bridge_policy(script)
    if str(policy.get("mode", "disabled") or "disabled").strip() != "required":
        return False

    clean = str(beat_id or "").strip()
    beat = script.beats.get(clean) or {}
    block_id = str(beat.get("block_id", "") or "").strip()

    excluded_beats = {
        str(item).strip()
        for item in policy.get("exclude_beat_ids", []) or []
        if str(item).strip()
    }
    excluded_blocks = {
        str(item).strip()
        for item in policy.get("exclude_block_ids", []) or []
        if str(item).strip()
    }
    if clean in excluded_beats or block_id in excluded_blocks:
        return False

    beat_ids = {
        str(item).strip()
        for item in policy.get("beat_ids", []) or []
        if str(item).strip()
    }
    block_ids = {
        str(item).strip()
        for item in policy.get("block_ids", []) or []
        if str(item).strip()
    }
    if beat_ids or block_ids:
        return clean in beat_ids or block_id in block_ids
    return True


def bridge_active(state: EditorialState) -> bool:
    return str(state.facts.get(_PHASE_KEY, "") or "") == "bridge"


def bridge_target_id(state: EditorialState) -> str:
    if not bridge_active(state):
        return ""
    return str(state.facts.get(_BRIDGE_TARGET_KEY, "") or "").strip()


def _dialogue_data(beat: Mapping[str, object]) -> tuple[str, str]:
    for unit in beat.get("units", []) or []:  # type: ignore[union-attr]
        if isinstance(unit, Mapping) and str(unit.get("kind", "")) == "dialogue":
            return (
                str(unit.get("anchor") or unit.get("text") or "").strip(),
                str(unit.get("instruction") or "").strip(),
            )
    return "", ""


def _is_structural_destination(script: EditorialScript, target_id: str) -> bool:
    if target_id in script.endings:
        return True
    target = script.beats.get(target_id) or {}
    return bool(str(target.get("terminal_yard_id", "") or "").strip())


def should_create_bridge(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> bool:
    origin = previous_state.node_id or script.first_beat_id
    target = str(turn.target_id or "").strip()
    if not bridge_enabled_for_beat(script, origin):
        return False
    if bridge_active(previous_state) or turn.finished:
        return False
    if not target or target == origin or target not in script.beats:
        return False
    return not _is_structural_destination(script, target)


def create_bridge_turn(
    script: EditorialScript,
    previous_state: EditorialState,
    proposed_turn: EditorialTurn,
    user_text: str,
) -> EditorialTurn:
    """Suspende o avanço e cria uma única resposta intermediária causal."""

    origin_id = previous_state.node_id or script.first_beat_id
    target_id = str(proposed_turn.target_id or "").strip()
    if not should_create_bridge(script, previous_state, proposed_turn):
        return proposed_turn

    target = script.beats.get(target_id) or {}
    canonical_line, dramatic_direction = _dialogue_data(target)
    updated = EditorialState.from_dict(proposed_turn.state.to_dict())
    updated.node_id = origin_id
    updated.pending_next_beat_id = target_id
    updated.interstitial_turns = 0
    updated.facts[_PHASE_KEY] = "bridge"
    updated.facts[_BRIDGE_ORIGIN_KEY] = origin_id
    updated.facts[_BRIDGE_TARGET_KEY] = target_id
    updated.facts[_BRIDGE_TURNS_KEY] = "1"
    updated.facts["_organic_interstitial"] = "false"

    prompt = "\n".join(
        (
            "FASE ESTRUTURAL: PONTE NARRATIVA.",
            "Responda genuinamente à fala mais recente do usuário na voz da personagem.",
            "A resposta deve parecer uma continuação natural da conversa, não uma fala de roteiro.",
            "Crie um gancho causal ou temático que prepare o próximo movimento, sem executá-lo.",
            "Não repita a linha canônica seguinte, não antecipe sua ação e não avance o local da cena.",
            "Não presuma ação, aceite, recusa, desejo ou decisão que o usuário não declarou.",
            "Termine deixando espaço real para outra resposta do usuário.",
            f"FALA ATUAL DO USUÁRIO: {str(user_text or '').strip()}",
            f"BEAT DE ORIGEM: {origin_id}",
            f"OBJETIVO FUTURO A PREPARAR, SEM REALIZAR: {str(target.get('objective', '') or '').strip()}",
            f"DIREÇÃO FUTURA, APENAS COMO CONTEXTO: {dramatic_direction}",
            f"LINHA FUTURA PROIBIDA NESTA RESPOSTA: {canonical_line}",
        )
    )
    return replace(
        proposed_turn,
        target_id=origin_id,
        visible_fallback=str(proposed_turn.visible_fallback or "").strip(),
        system_prompt=prompt,
        state=updated,
        finished=False,
        run_status="active",
        ending_code="",
    )


def release_bridge_state(script: EditorialScript, state: EditorialState) -> EditorialState:
    """Libera exatamente o destino preparado para o próximo turno canônico."""

    target_id = bridge_target_id(state)
    if not target_id:
        raise RuntimeError("Estado de ponte ativo sem beat alvo declarado.")
    if target_id not in script.beats:
        raise RuntimeError(f"Ponte aponta para beat inexistente: {target_id!r}")

    updated = EditorialState.from_dict(state.to_dict())
    updated.pending_next_beat_id = target_id
    updated.facts[_PHASE_KEY] = "canonical"
    for key in (_BRIDGE_ORIGIN_KEY, _BRIDGE_TARGET_KEY, _BRIDGE_TURNS_KEY):
        updated.facts.pop(key, None)
    return updated


__all__ = [
    "bridge_active",
    "bridge_enabled_for_beat",
    "bridge_policy",
    "bridge_target_id",
    "create_bridge_turn",
    "release_bridge_state",
    "should_create_bridge",
]
