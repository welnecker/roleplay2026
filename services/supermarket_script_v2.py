from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

import services.pilot_supermarket as pilot_supermarket_module
from services.narrative_context import build_narrative_context
from services.organic_interaction import detect_organic_signal, extract_user_facts, render_facts
from services.pilot_supermarket import (
    PilotScript,
    PilotState,
    PilotTurn,
    classify_user_message as base_classify_user_message,
    clean_model_response as base_clean_model_response,
    decide_turn as base_decide_turn,
)
from services.supermarket_intent_pilot import classify_supermarket_intent


_AUTOMATIC_FOLLOWUPS: dict[str, tuple[dict[str, str], ...]] = {}
_SEXUAL_CONTEXT_TERMS = (
    "chupa", "chupar", "fode", "foder", "goza", "gozar", "gostosa", "gostoso",
    "delícia", "delicia", "tesão", "tesao", "pau", "rola", "xoxota", "buceta",
)
_CONTEXTUAL_INSULT_TERMS = ("vadia", "vagabunda")
_DIRECT_ABUSE_PATTERNS = (
    "você é uma vadia", "voce e uma vadia", "sua vadia", "você é vagabunda",
    "voce e vagabunda", "sua vagabunda",
)
_STRICT_MOTEL_BEAT = re.compile(r"^motel_\d+$")


def _is_strict_motel_beat(beat_id: str) -> bool:
    return bool(_STRICT_MOTEL_BEAT.fullmatch(str(beat_id or "").strip()))


def _humanize_scene_location(value: str) -> str:
    words = [part for part in value.strip().split("_") if part]
    return " ".join(words).capitalize() if words else ""


def _transition_metadata(item: dict[str, Any]) -> tuple[str, str]:
    transition = item.get("transition") if isinstance(item.get("transition"), dict) else {}
    time_label = str(transition.get("time", "") or "").strip() or "Algum tempo depois"
    location_label = str(transition.get("location", "") or "").strip()
    if not location_label:
        location_label = _humanize_scene_location(str(item.get("scene_location", "") or ""))
    return time_label, location_label


def render_automatic_followup_text(followup: dict[str, str]) -> str:
    text = str(followup.get("text", "") or "").strip()
    heading = " — ".join(
        part for part in (
            str(followup.get("transition_time", "") or "").strip(),
            str(followup.get("transition_location", "") or "").strip(),
        ) if part
    )
    return f"[{heading.upper()}]\n\n{text}" if heading else text


def _register_automatic_followups(script: PilotScript) -> None:
    registered: dict[str, tuple[dict[str, str], ...]] = {}
    for block in script.raw.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            followups: list[dict[str, str]] = []
            for item in beat.get("automatic_followups", []) or []:
                if not isinstance(item, dict):
                    continue
                target_id = str(item.get("target_id", "")).strip()
                raw_text = str(item.get("text", "")).strip()
                if not target_id or not raw_text:
                    raise ValueError(f"Ponte automática inválida no beat {beat_id!r}.")
                time_label, location_label = _transition_metadata(item)
                followup = {
                    "target_id": target_id,
                    "text": raw_text,
                    "scene_location": str(item.get("scene_location", "")).strip(),
                    "transition_time": time_label,
                    "transition_location": location_label,
                }
                followup["text"] = render_automatic_followup_text(followup)
                followups.append(followup)
            if followups:
                registered[beat_id] = tuple(followups)
    _AUTOMATIC_FOLLOWUPS.clear()
    _AUTOMATIC_FOLLOWUPS.update(registered)


def prepare_supermarket_script_v2(script: PilotScript) -> PilotScript:
    _register_automatic_followups(script)
    pilot_supermarket_module.classify_user_message = classify_contextual_user_message
    return script


def classify_contextual_user_message(text: str) -> str:
    engagement = base_classify_user_message(text)
    if engagement != "hostile":
        return engagement
    value = " ".join(str(text or "").casefold().split())
    if any(pattern in value for pattern in _DIRECT_ABUSE_PATTERNS):
        return engagement
    contextual = any(term in value for term in _CONTEXTUAL_INSULT_TERMS)
    sexual = any(term in value for term in _SEXUAL_CONTEXT_TERMS)
    return "engaged" if contextual and sexual else engagement


def _memory_ids(state: PilotState) -> list[str]:
    return [
        item.strip()
        for item in str(state.facts.get("_active_memory_ids", "") or "").split(",")
        if item.strip()
    ]


def _memory_writes_for_target(script: PilotScript, target_id: str) -> list[str]:
    source = script.beats.get(target_id) or script.endings.get(target_id) or {}
    return [str(item).strip() for item in source.get("memory_writes", []) or [] if str(item).strip()]


def _finalize_turn(script: PilotScript, turn: PilotTurn) -> PilotTurn:
    previous_ids = _memory_ids(turn.state)
    context = build_narrative_context(script.raw, previous_ids, turn.state.facts)
    writes = _memory_writes_for_target(script, turn.target_id)
    updated = PilotState.from_dict(turn.state.to_dict())
    updated.facts["_active_memory_ids"] = ",".join(dict.fromkeys([*previous_ids, *writes]))
    updated.facts["_pending_memory_writes"] = ",".join(writes)

    strict_motel = _is_strict_motel_beat(turn.target_id)
    updated.facts["_force_fixed_response"] = "false"
    updated.facts["_strict_motel_canonical"] = "true" if strict_motel else "false"

    prompt = turn.system_prompt
    if strict_motel:
        prompt = (
            f"{prompt}\n\nCONTINUIDADE ESTRITA DO MOTEL:\n"
            "- Responda primeiro ao conteúdo específico do usuário em uma ou duas frases curtas e naturais.\n"
            "- Em seguida, entregue a linha canônica do movimento atual, preservando integralmente seu sentido e sua ação.\n"
            "- A reação e a linha canônica devem formar uma única fala contínua.\n"
            "- Não antecipe nenhuma ação, posição, penetração, orgasmo, despedida ou acontecimento de beats posteriores.\n"
            "- Não acrescente nada depois da linha canônica.\n"
            "- Não abra uma nova pergunta além da que já existir na própria linha canônica."
        )
    return replace(turn, state=updated, system_prompt=f"{context}\n\n{prompt}".strip())


def _normal_target(script: PilotScript, state: PilotState, engagement: str) -> str:
    current_id = state.node_id or script.first_beat_id
    beat = script.beats.get(current_id) or {}
    transitions = beat.get("on_user") or {}
    return str(
        transitions.get(engagement)
        or transitions.get("engaged")
        or beat.get("terminal_transition")
        or ""
    )


def _state_with_extracted_facts(state: PilotState, user_text: str) -> PilotState:
    updated = PilotState.from_dict(state.to_dict())
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


def _resolve_declared_target(
    script: PilotScript,
    initial_target: str,
    facts: dict[str, str],
) -> tuple[str, tuple[str, ...]]:
    """Resolve saltos sobre o alvo efetivo, aceita cadeia e rejeita ciclos/IDs inválidos."""

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


def _routing_state_for_declared_skips(
    script: PilotScript,
    state: PilotState,
    engagement: str,
    *,
    original_facts: dict[str, str],
) -> PilotState:
    initial_target = state.pending_next_beat_id or _normal_target(script, state, engagement)
    final_target, skipped = _resolve_declared_target(script, initial_target, state.facts)
    if not skipped:
        return state

    routed = PilotState.from_dict(state.to_dict())
    routed.pending_next_beat_id = final_target
    routed.facts["_declared_skip_applied"] = ",".join(skipped)

    # Itera sobre uma fotografia estável porque as marcações de reconhecimento
    # são adicionadas ao mesmo dicionário durante este processamento.
    for fact_name, value in list(routed.facts.items()):
        if fact_name.startswith("_") or original_facts.get(fact_name) == value:
            continue
        routed.facts[f"_acknowledged_{fact_name}"] = value
    return routed


def _organic_slack_enabled(script: PilotScript) -> bool:
    raw = script.raw.get("organic_slack") or {}
    return isinstance(raw, dict) and bool(raw.get("enabled", False))


def _organic_slack_turn(script: PilotScript, state: PilotState, user_text: str) -> PilotTurn | None:
    if not _organic_slack_enabled(script) or state.pending_next_beat_id or state.interstitial_turns >= 1:
        return None
    current_id = state.node_id or script.first_beat_id
    if current_id == "reencontro_fila_007" or _is_strict_motel_beat(current_id):
        return None
    signal = detect_organic_signal(user_text, state.facts)
    if signal is None or signal.kind != "free_reaction":
        return None
    engagement = classify_contextual_user_message(user_text)
    if engagement in {"hostile", "mocking"}:
        return None
    next_id = _normal_target(script, state, engagement)
    if not next_id:
        return None

    updated = PilotState.from_dict(state.to_dict())
    updated.facts = signal.facts
    updated.facts["_organic_interstitial"] = "true"
    updated.pending_next_beat_id = next_id
    updated.interstitial_turns = 1
    prompt = (
        "Você é Mary. Este é um TURNO ORGÂNICO INTERMEDIÁRIO.\n"
        "Responda somente ao que o usuário acabou de dizer, com liberdade emocional e continuidade.\n"
        "Permaneça no mesmo local, momento e eixo narrativo.\n"
        "Não execute, não cite, não parafraseie e não misture a próxima linha canônica.\n"
        "Não avance tempo, local ou acontecimento. A próxima linha do roteiro será retomada em outro turno.\n"
        f"FATOS CONFIRMADOS: {render_facts(updated.facts)}\n"
        f"MENSAGEM DO USUÁRIO: {user_text}\n"
        f"ORIENTAÇÃO DE REAÇÃO: {signal.instruction}"
    )
    return PilotTurn(
        engagement=engagement,  # type: ignore[arg-type]
        target_id=current_id,
        visible_fallback=signal.fallback,
        system_prompt=prompt,
        state=updated,
    )


def _repeat_help_request(script: PilotScript, state: PilotState, user_text: str) -> PilotTurn:
    beat = script.beats["reencontro_fila_007"]
    fallback = next(
        (
            str(unit.get("anchor") or unit.get("text") or "")
            for unit in beat.get("units") or []
            if isinstance(unit, dict) and unit.get("kind") == "dialogue"
        ),
        "",
    )
    updated = PilotState.from_dict(state.to_dict())
    updated.node_id = "reencontro_fila_007"
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    updated.facts["_scene_location"] = "supermercado_caixa"
    updated.facts["_organic_interstitial"] = "false"
    return _finalize_turn(
        script,
        PilotTurn(
            engagement=classify_contextual_user_message(user_text),  # type: ignore[arg-type]
            target_id="reencontro_fila_007",
            visible_fallback=fallback,
            system_prompt=(
                "Você é Mary, ainda no caixa. Responda brevemente e confirme se o usuário vai esperar. "
                "Não presuma aceite e não avance ao estacionamento. Preserve o movimento editorial fornecido."
            ),
            state=updated,
        ),
    )


def decide_supermarket_script_v2_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Decide a transição usando fatos e regras declaradas pelo roteiro."""

    original_facts = dict(state.facts)
    working_state = _state_with_extracted_facts(state, user_text)

    organic = _organic_slack_turn(script, working_state, user_text)
    if organic is not None:
        return _finalize_turn(script, organic)

    current_id = working_state.node_id or script.first_beat_id
    if current_id == "reencontro_fila_007":
        intent = classify_supermarket_intent(current_id, user_text)
        if intent == "accept":
            turn = base_decide_turn(script, working_state, user_text)
            updated = PilotState.from_dict(turn.state.to_dict())
            updated.facts["help_to_car"] = "accepted"
            updated.facts["_scene_location"] = "estacionamento_caminho"
            updated.facts["_organic_interstitial"] = "false"
            return _finalize_turn(script, replace(turn, state=updated))
        if intent == "refuse":
            from services.supermarket_intent_pilot import decide_supermarket_turn

            turn = decide_supermarket_turn(script, working_state, user_text)
            updated = PilotState.from_dict(turn.state.to_dict())
            updated.facts["_organic_interstitial"] = "false"
            return _finalize_turn(script, replace(turn, state=updated))
        return _repeat_help_request(script, working_state, user_text)

    engagement = classify_contextual_user_message(user_text)
    routing_state = _routing_state_for_declared_skips(
        script,
        working_state,
        engagement,
        original_facts=original_facts,
    )
    turn = base_decide_turn(script, routing_state, user_text)
    updated = PilotState.from_dict(turn.state.to_dict())
    updated.facts["_organic_interstitial"] = "false"
    return _finalize_turn(script, replace(turn, state=updated))


def automatic_followups_after(target_id: str) -> tuple[dict[str, str], ...]:
    return _AUTOMATIC_FOLLOWUPS.get(str(target_id), ())


def state_after_automatic_followup(state: PilotState, followup: dict[str, str]) -> PilotState:
    updated = PilotState.from_dict(state.to_dict())
    updated.node_id = str(followup["target_id"])
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    updated.facts["_organic_interstitial"] = "false"
    location = str(followup.get("scene_location", ""))
    if location:
        updated.facts["_scene_location"] = location
    if updated.node_id.startswith("retorno_casa_"):
        updated.facts["alfredinho_has_voice"] = "false"
    if updated.node_id == "mensagens_iniciais_001":
        updated.facts["active_interlocutor"] = "janio"
        updated.facts["alfredinho_has_voice"] = "false"
    return updated


def clean_supermarket_script_v2_response(response: str, fallback: str) -> str:
    return base_clean_model_response(response, fallback)