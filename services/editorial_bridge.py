from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Mapping

from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_semantic_reconciliation import reconciled_step

_PHASE_KEY = "_runtime_phase"
_BRIDGE_ORIGIN_KEY = "_bridge_origin_beat_id"
_BRIDGE_TARGET_KEY = "_bridge_target_beat_id"
_BRIDGE_TURNS_KEY = "_bridge_turn_count"
_BRIDGE_ORIGIN_OBJECTIVE_KEY = "_bridge_origin_objective"
_BRIDGE_ORIGIN_CANONICAL_KEY = "_bridge_origin_canonical"
_BRIDGE_TARGET_OBJECTIVE_KEY = "_bridge_target_objective"
_BRIDGE_TARGET_CANONICAL_KEY = "_bridge_target_canonical"
_BRIDGE_STEP_INDEX_KEY = "_bridge_step_index"
_BRIDGE_STEP_ID_KEY = "_bridge_step_id"
_BRIDGE_STEP_INSTRUCTION_KEY = "_bridge_step_instruction"
_BRIDGE_ALLOW_QUESTION_KEY = "_bridge_allow_question"
_BRIDGE_FALLBACK = (
    "Ela reage ao que você disse sem apressar o próximo passo, sem repetir o que acabou de acontecer nem antecipar o destino."
)


def bridge_policy(script: EditorialScript) -> dict[str, Any]:
    direct = script.raw.get("bridge_policy") or {}
    if isinstance(direct, dict) and direct:
        return direct

    runtime_policy = script.raw.get("organic_slack") or {}
    if not isinstance(runtime_policy, dict):
        return {}
    nested = runtime_policy.get("bridge_policy") or {}
    return nested if isinstance(nested, dict) else {}


def automatic_gate_policy(script: EditorialScript) -> dict[str, Any]:
    policy = script.raw.get("automatic_gate_policy") or {}
    return policy if isinstance(policy, dict) else {}


def automatic_gate_enabled(script: EditorialScript) -> bool:
    return bool(automatic_gate_policy(script).get("enabled", False))


def bridge_enabled_for_beat(script: EditorialScript, beat_id: str) -> bool:
    """Ativa a ponte somente onde o card declarou a nova máquina de estados."""

    if automatic_gate_enabled(script):
        beat = script.beats.get(str(beat_id or "").strip()) or {}
        return not bool(str(beat.get("terminal_yard_id", "") or "").strip())

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


def _beat_semantics(beat: Mapping[str, object]) -> tuple[str, str, str]:
    canonical, direction = _dialogue_data(beat)
    objective = str(
        beat.get("objective")
        or beat.get("required_movement")
        or ""
    ).strip()
    return objective, canonical, direction


def _authored_bridges(beat: Mapping[str, object]) -> list[dict[str, str]]:
    bridges: list[dict[str, str]] = []
    for position, item in enumerate(beat.get("authored_bridges", []) or []):  # type: ignore[union-attr]
        if not isinstance(item, Mapping):
            continue
        instruction = str(item.get("instruction", "") or "").strip()
        if not instruction:
            continue
        bridges.append(
            {
                "bridge_id": str(item.get("bridge_id", "") or f"bridge_{position + 1}"),
                "instruction": instruction,
                "index": str(position),
            }
        )
    return bridges


def _bridge_may_ask(instruction: str) -> bool:
    return bool(
        re.search(
            r"\beu\s+(?:pergunt\w*|peç\w*|pec\w*|solicit\w*|question\w*)",
            str(instruction or ""),
            flags=re.IGNORECASE,
        )
    )


def _store_bridge_step(facts: dict[str, str], step: Mapping[str, str], index: int) -> None:
    instruction = str(step.get("instruction", "") or "").strip()
    facts[_BRIDGE_STEP_INDEX_KEY] = str(index)
    facts[_BRIDGE_STEP_ID_KEY] = str(step.get("bridge_id", "") or "").strip()
    facts[_BRIDGE_STEP_INSTRUCTION_KEY] = instruction
    facts[_BRIDGE_ALLOW_QUESTION_KEY] = "true" if _bridge_may_ask(instruction) else "false"


def _bridge_prompt(
    *,
    user_text: str,
    origin_id: str,
    target_id: str,
    origin_objective: str,
    origin_canonical: str,
    target_objective: str,
    target_canonical: str,
    bridge_id: str,
    bridge_instruction: str,
    allow_question: bool,
    reconciliation: str = "",
) -> str:
    question_rule = (
        "Esta etapa autoral pode fazer a pergunta indispensável à sua finalidade, no máximo uma."
        if allow_question
        else "Não crie pergunta, promessa, dúvida ou obstáculo que abra uma pendência artificial."
    )
    lines = [
            "FASE ESTRUTURAL: PONTE NARRATIVA AUTORAL SEQUENCIAL.",
            f"ETAPA DE PONTE ATUAL: {bridge_id}",
            f"FINALIDADE AUTORAL OBRIGATÓRIA DESTA ETAPA: {bridge_instruction}",
            "Responda genuinamente à fala mais recente do usuário na voz da personagem e cumpra esta finalidade.",
            "A ponte não é uma segunda versão do beat anterior nem uma prévia do seguinte.",
            "Se o usuário já tiver satisfeito a finalidade, reconheça e aproveite o que ele declarou; não repita pedido, pergunta ou informação.",
            "A ponte deve aproximar a conversa da meta global sem executar o beat de destino.",
            "Use no máximo duas frases curtas: responda diretamente e, somente se necessário, retome a única pendência atual.",
            "Não acrescente promessa, entusiasmo genérico, explicação ornamental, nova provocação ou gancho conversacional.",
            question_rule,
            "Não presuma ação, aceite, recusa, desejo, excitação ou decisão que o usuário não declarou.",
            f"FALA ATUAL DO USUÁRIO: {str(user_text or '').strip()}",
            f"BEAT DE ORIGEM: {origin_id}",
            f"MOVIMENTO DE ORIGEM JÁ CONCLUÍDO — PROIBIDO REPETIR: {origin_objective}",
            f"LINHA DE ORIGEM JÁ CONSUMIDA — PROIBIDO PARAFRASEAR: {origin_canonical}",
            f"BEAT DE DESTINO: {target_id}",
            f"OBJETIVO FUTURO RESERVADO AO DESTINO — PROIBIDO EXECUTAR: {target_objective}",
            f"LINHA FUTURA PROIBIDA NESTA RESPOSTA: {target_canonical}",
    ]
    if reconciliation:
        lines.extend(("RECONCILIAÇÃO COM A CONVERSA:", reconciliation))
    return "\n".join(lines)


def _pending_authored_bridges(
    state: EditorialState,
    authored: list[dict[str, str]],
    *,
    after_index: int = -1,
) -> list[tuple[dict[str, str], str]]:
    pending: list[tuple[dict[str, str], str]] = []
    for step in authored:
        index = int(step.get("index", "0") or 0)
        if index <= after_index:
            continue
        assessment = reconciled_step(state, step["bridge_id"])
        if assessment.status == "satisfied":
            continue
        detail = ""
        if assessment.status == "partial":
            detail = (
                f"Parte já satisfeita por: {assessment.evidence}. "
                f"Execute somente o restante: {assessment.remaining_intent}. "
                f"Não repita: {', '.join(assessment.suppress)}."
            )
        elif assessment.status == "contradicted":
            detail = (
                f"O usuário contradisse esta finalidade por: {assessment.evidence}. "
                "Reaja apenas de modo recuperável, sem insistir nem criar outra trajetória."
            )
        pending.append((step, detail))
    return pending


def _is_structural_destination(script: EditorialScript, target_id: str) -> bool:
    if target_id in script.endings:
        return True
    target = script.beats.get(target_id) or {}
    return bool(str(target.get("terminal_yard_id", "") or "").strip())


def _requires_integrated_canonical_response(
    script: EditorialScript,
    target_id: str,
) -> bool:
    """Indica que o próximo beat deve reagir e avançar na mesma resposta.

    Beats conclusivos ou semanticamente indivisíveis não recebem ponte: uma
    resposta intermediária consumiria parte do objetivo e provocaria repetição.
    """

    target = script.beats.get(str(target_id or "").strip()) or {}
    boundary = str(target.get("response_boundary", "") or "").strip()
    return boundary == "integrated_canonical"


def _is_resolved_runtime_transition(
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> bool:
    """Reconhece apenas resoluções produzidas no beat do turno atual."""

    origin = str(previous_state.node_id or "").strip()
    facts = turn.state.facts

    explicit = str(facts.get("_last_user_explicit_decision", "") or "") == "true"
    explicit_origin = str(facts.get("_last_user_intent_beat_id", "") or "").strip()
    if explicit and explicit_origin == origin:
        return True

    skipped = bool(str(facts.get("_declared_skip_applied", "") or "").strip())
    skip_origin = str(facts.get("_declared_skip_origin_beat_id", "") or "").strip()
    semantic_skipped = bool(
        str(facts.get("_semantic_skip_applied", "") or "").strip()
    )
    semantic_origin = str(
        facts.get("_semantic_skip_origin_beat_id", "") or ""
    ).strip()
    return (skipped and skip_origin == origin) or (
        semantic_skipped and semantic_origin == origin
    )


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
    if _is_resolved_runtime_transition(previous_state, turn):
        return False
    if not target or target == origin or target not in script.beats:
        return False
    if _requires_integrated_canonical_response(script, target):
        return False
    origin_beat = script.beats.get(origin) or {}
    authored_bridge = bool(origin_beat.get("has_authored_bridge", False))
    if automatic_gate_enabled(script) and not authored_bridge:
        assessment = reconciled_step(turn.state, origin)
        return assessment.status in {"pending", "partial"}
    return authored_bridge or not _is_structural_destination(script, target)


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

    origin = script.beats.get(origin_id) or {}
    target = script.beats.get(target_id) or {}
    origin_objective, origin_canonical, _origin_direction = _beat_semantics(origin)
    target_objective, target_canonical, _target_direction = _beat_semantics(target)
    authored = _authored_bridges(origin)
    pending_authored = _pending_authored_bridges(proposed_turn.state, authored)
    if authored and not pending_authored:
        return proposed_turn
    assessment = reconciled_step(proposed_turn.state, origin_id)
    automatic_instruction = (
        "Eu respondo ao conteúdo real de {{nome}} e resolvo a finalidade ainda pendente "
        "deste movimento. Se houver uma solicitação ou pergunta sem decisão, eu a retomo "
        "naturalmente uma única vez, sem presumir aceite e sem avançar ao próximo beat."
    )
    first_step, reconciliation = pending_authored[0] if pending_authored else ({
        "bridge_id": f"{origin_id}__bridge",
        "instruction": automatic_instruction if automatic_gate_enabled(script) else _BRIDGE_FALLBACK,
        "index": "0",
    }, (
        f"Finalidade ainda pendente: {assessment.remaining_intent or origin_objective}. "
        f"Evidência do usuário: {assessment.evidence or 'nenhuma decisão suficiente'}."
        if automatic_gate_enabled(script) else ""
    ))

    updated = EditorialState.from_dict(proposed_turn.state.to_dict())
    updated.node_id = origin_id
    updated.pending_next_beat_id = target_id
    updated.interstitial_turns = 0
    updated.facts[_PHASE_KEY] = "bridge"
    updated.facts[_BRIDGE_ORIGIN_KEY] = origin_id
    updated.facts[_BRIDGE_TARGET_KEY] = target_id
    updated.facts[_BRIDGE_TURNS_KEY] = "1"
    updated.facts[_BRIDGE_ORIGIN_OBJECTIVE_KEY] = origin_objective
    updated.facts[_BRIDGE_ORIGIN_CANONICAL_KEY] = origin_canonical
    updated.facts[_BRIDGE_TARGET_OBJECTIVE_KEY] = target_objective
    updated.facts[_BRIDGE_TARGET_CANONICAL_KEY] = target_canonical
    _store_bridge_step(updated.facts, first_step, int(first_step.get("index", "0") or 0))
    updated.facts["_organic_interstitial"] = "false"
    if automatic_gate_enabled(script) and not authored:
        updated.facts["_automatic_gate_active"] = "true"
        updated.facts["_automatic_gate_origin_id"] = origin_id
        updated.facts["_automatic_gate_attempts"] = "1"

    prompt = _bridge_prompt(
        user_text=user_text,
        origin_id=origin_id,
        target_id=target_id,
        origin_objective=origin_objective,
        origin_canonical=origin_canonical,
        target_objective=target_objective,
        target_canonical=target_canonical,
        bridge_id=first_step["bridge_id"],
        bridge_instruction=first_step["instruction"],
        allow_question=(
            True if automatic_gate_enabled(script) and not authored
            else _bridge_may_ask(first_step["instruction"])
        ),
        reconciliation=reconciliation,
    )
    return replace(
        proposed_turn,
        target_id=origin_id,
        visible_fallback=_BRIDGE_FALLBACK,
        system_prompt=prompt,
        state=updated,
        finished=False,
        run_status="active",
        ending_code="",
    )


def advance_authored_bridge_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    engagement: str,
) -> EditorialTurn | None:
    """Executa a próxima [PONTE] do mesmo beat em um turno independente."""

    if not bridge_active(state):
        return None
    origin_id = str(state.facts.get(_BRIDGE_ORIGIN_KEY, "") or "").strip()
    target_id = bridge_target_id(state)
    origin = script.beats.get(origin_id) or {}
    authored = _authored_bridges(origin)
    current_index = int(state.facts.get(_BRIDGE_STEP_INDEX_KEY, "0") or 0)
    pending_authored = _pending_authored_bridges(
        state,
        authored,
        after_index=current_index,
    )
    if not pending_authored:
        return None

    step, reconciliation = pending_authored[0]
    next_index = int(step.get("index", "0") or 0)
    updated = EditorialState.from_dict(state.to_dict())
    updated.facts[_BRIDGE_TURNS_KEY] = str(next_index + 1)
    _store_bridge_step(updated.facts, step, next_index)
    prompt = _bridge_prompt(
        user_text=user_text,
        origin_id=origin_id,
        target_id=target_id,
        origin_objective=str(updated.facts.get(_BRIDGE_ORIGIN_OBJECTIVE_KEY, "") or ""),
        origin_canonical=str(updated.facts.get(_BRIDGE_ORIGIN_CANONICAL_KEY, "") or ""),
        target_objective=str(updated.facts.get(_BRIDGE_TARGET_OBJECTIVE_KEY, "") or ""),
        target_canonical=str(updated.facts.get(_BRIDGE_TARGET_CANONICAL_KEY, "") or ""),
        bridge_id=step["bridge_id"],
        bridge_instruction=step["instruction"],
        allow_question=_bridge_may_ask(step["instruction"]),
        reconciliation=reconciliation,
    )
    return EditorialTurn(
        engagement=engagement,  # type: ignore[arg-type]
        target_id=origin_id,
        visible_fallback=_BRIDGE_FALLBACK,
        system_prompt=prompt,
        state=updated,
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
    for key in (
        _BRIDGE_ORIGIN_KEY,
        _BRIDGE_TARGET_KEY,
        _BRIDGE_TURNS_KEY,
        _BRIDGE_ORIGIN_OBJECTIVE_KEY,
        _BRIDGE_ORIGIN_CANONICAL_KEY,
        _BRIDGE_TARGET_OBJECTIVE_KEY,
        _BRIDGE_TARGET_CANONICAL_KEY,
        _BRIDGE_STEP_INDEX_KEY,
        _BRIDGE_STEP_ID_KEY,
        _BRIDGE_STEP_INSTRUCTION_KEY,
        _BRIDGE_ALLOW_QUESTION_KEY,
        "_automatic_gate_active",
        "_automatic_gate_origin_id",
        "_automatic_gate_attempts",
    ):
        updated.facts.pop(key, None)
    return updated


__all__ = [
    "automatic_gate_enabled",
    "automatic_gate_policy",
    "bridge_active",
    "advance_authored_bridge_turn",
    "bridge_enabled_for_beat",
    "bridge_policy",
    "bridge_target_id",
    "create_bridge_turn",
    "release_bridge_state",
    "should_create_bridge",
]
