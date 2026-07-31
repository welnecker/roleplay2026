from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.pilot_supermarket import (
    PilotScript,
    PilotState,
    PilotTurn,
    classify_user_message,
    clean_model_response as base_clean_model_response,
    decide_turn as base_decide_turn,
)
from services.supermarket_intent_pilot import classify_supermarket_intent


_AUTOMATIC_FOLLOWUPS: dict[str, tuple[dict[str, str], ...]] = {}


def _humanize_scene_location(value: str) -> str:
    """Converte o identificador técnico de local em legenda visível neutra."""

    words = [part for part in value.strip().split("_") if part]
    if not words:
        return ""
    return " ".join(words).capitalize()


def _transition_metadata(item: dict[str, Any]) -> tuple[str, str]:
    """Lê tempo e local formais da ponte, com fallback editorial seguro."""

    raw_transition = item.get("transition")
    transition = raw_transition if isinstance(raw_transition, dict) else {}
    time_label = str(transition.get("time", "") or "").strip()
    location_label = str(transition.get("location", "") or "").strip()
    scene_location = str(item.get("scene_location", "") or "").strip()

    if not time_label:
        time_label = "Algum tempo depois"
    if not location_label:
        location_label = _humanize_scene_location(scene_location)
    return time_label, location_label


def render_automatic_followup_text(followup: dict[str, str]) -> str:
    """Produz a mensagem persistida com transição de tempo/local antes da fala."""

    text = str(followup.get("text", "") or "").strip()
    time_label = str(followup.get("transition_time", "") or "").strip()
    location_label = str(followup.get("transition_location", "") or "").strip()
    heading = " — ".join(part for part in (time_label, location_label) if part)
    if not heading:
        return text
    return f"[{heading.upper()}]\n\n{text}"


def _register_automatic_followups(script: PilotScript) -> None:
    """Indexa somente a mecânica declarada na fonte editorial."""

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
                text = str(item.get("text", "")).strip()
                if not target_id or not text:
                    raise ValueError(f"Ponte automática inválida no beat {beat_id!r}.")
                time_label, location_label = _transition_metadata(item)
                followups.append(
                    {
                        "target_id": target_id,
                        "text": text,
                        "scene_location": str(item.get("scene_location", "")).strip(),
                        "transition_time": time_label,
                        "transition_location": location_label,
                    }
                )
            if followups:
                registered[beat_id] = tuple(followups)
    _AUTOMATIC_FOLLOWUPS.clear()
    _AUTOMATIC_FOLLOWUPS.update(registered)


def prepare_supermarket_script_v2(script: PilotScript) -> PilotScript:
    """Valida e indexa a fonte sem alterar nenhum beat ou fala."""

    _register_automatic_followups(script)
    return script


def _repeat_help_request(script: PilotScript, state: PilotState, user_text: str) -> PilotTurn:
    beat = script.beats["reencontro_fila_007"]
    fallback = str(beat.get("anchor") or beat.get("canonical_line") or "")
    updated = PilotState.from_dict(state.to_dict())
    updated.node_id = "reencontro_fila_007"
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    updated.facts["_scene_location"] = "supermercado_caixa"
    return PilotTurn(
        engagement=classify_user_message(user_text),
        target_id="reencontro_fila_007",
        visible_fallback=fallback,
        system_prompt=(
            "Você é Mary, ainda no caixa. Responda brevemente e confirme se o usuário vai esperar. "
            "Não presuma aceite e não avance ao estacionamento. Preserve o movimento editorial fornecido."
        ),
        state=updated,
    )


def decide_supermarket_script_v2_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Aplica somente decisões de interação; o conteúdo pertence ao roteiro."""

    current_id = state.node_id or script.first_beat_id
    if current_id == "reencontro_fila_007":
        intent = classify_supermarket_intent(current_id, user_text)
        if intent == "accept":
            synthetic = PilotState.from_dict(state.to_dict())
            synthetic.node_id = "reencontro_fila_008"
            turn = base_decide_turn(script, synthetic, user_text)
            updated = PilotState.from_dict(turn.state.to_dict())
            updated.facts["help_to_car"] = "accepted"
            updated.facts["_scene_location"] = "estacionamento_caminho"
            return replace(turn, state=updated)
        if intent == "refuse":
            from services.supermarket_intent_pilot import decide_supermarket_turn

            return decide_supermarket_turn(script, state, user_text)
        return _repeat_help_request(script, state, user_text)

    return base_decide_turn(script, state, user_text)


def automatic_followups_after(target_id: str) -> tuple[dict[str, str], ...]:
    return _AUTOMATIC_FOLLOWUPS.get(str(target_id), ())


def state_after_automatic_followup(state: PilotState, followup: dict[str, str]) -> PilotState:
    updated = PilotState.from_dict(state.to_dict())
    updated.node_id = str(followup["target_id"])
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
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
