from __future__ import annotations

from dataclasses import replace
import re
from typing import Any, Literal

from services.pilot_supermarket import (
    PilotScript,
    PilotState,
    PilotTurn,
    classify_user_message,
    decide_turn,
)

UserIntent = Literal["accept", "refuse", "postpone", "question", "unclear"]
SUPERMARKET_PILOT_VERSION = "1.1.0-memory-yard"

_SUPERMARKET_LOCATIONS = {
    "encontro_acidental_001": "supermercado_corredor",
    "encontro_acidental_002": "supermercado_corredor",
    "encontro_acidental_003": "supermercado_corredor",
    "encontro_acidental_004": "supermercado_corredor",
    "reencontro_fila_001": "supermercado_fila",
    "reencontro_fila_002": "supermercado_fila",
    "reencontro_fila_003": "supermercado_fila",
    "reencontro_fila_004": "supermercado_fila",
    "reencontro_fila_005": "supermercado_fila",
    "reencontro_fila_006": "supermercado_caixa",
    "reencontro_fila_007": "supermercado_caixa",
    "reencontro_fila_008": "estacionamento_caminho",
    "reencontro_fila_009": "estacionamento_carro_mary",
    "yard_help_refused_001": "supermercado_caixa",
    "yard_help_refused_002": "supermercado_caixa",
}

_ACCEPT_PATTERNS = (
    r"\b(?:sim|claro|beleza|com certeza|pode deixar|eu ajudo|vou ajudar|te ajudo|vamos|bora)\b",
    r"\b(?:vou esperar|espero aqui|pode contar comigo)\b",
)
_REFUSE_PATTERNS = (
    r"\b(?:não|nao)\s+(?:posso|consigo|vou|quero|dá|da)\b",
    r"\b(?:prefiro não|melhor não|não vai dar|não dá|não consigo|não quero)\b",
)
_POSTPONE_PATTERNS = (
    r"\b(?:agora não|depois|mais tarde|outra hora|estou com pressa|tô com pressa|to com pressa)\b",
)


def apply_supermarket_document_overrides(document: dict[str, Any]) -> dict[str, Any]:
    document["script_version"] = SUPERMARKET_PILOT_VERSION
    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            if beat_id == "encontro_acidental_004":
                beat["required_movement"] = (
                    "Mary encerra o primeiro contato de forma simpática, sem verbalizar "
                    "pensamentos íntimos nem antecipar interesse romântico."
                )
                beat["canonical_line"] = "Tchauzinho..."
                beat["dramatic_direction"] = (
                    "Despedida breve e natural. Não incluir pensamento, carência ou "
                    "comentário sobre a aparência do usuário."
                )
                beat["max_sentences"] = 2
            elif beat_id == "reencontro_fila_007":
                beat["required_movement"] = (
                    "Mary pede ajuda até o carro e aguarda decisão explícita. "
                    "Não presumir que o usuário aceitou."
                )
                beat["dramatic_direction"] = (
                    "Perguntar com naturalidade e aguardar aceite, recusa, adiamento ou dúvida."
                )
            elif beat_id == "reencontro_fila_008":
                beat["required_movement"] = (
                    "Somente após aceite confirmado, Mary segue com o usuário e o carrinho "
                    "em direção ao carro."
                )
            elif beat_id == "reencontro_fila_009":
                beat["required_movement"] = "Mary e o usuário chegam ao carro de Mary."
    return document


def prepare_supermarket_script(script: PilotScript) -> PilotScript:
    request = script.beats.get("reencontro_fila_007")
    if request:
        request["objective"] = (
            "Mary pede ajuda até o carro e aguarda uma decisão explícita. "
            "Não presumir que o usuário aceitou."
        )
    return script


def classify_supermarket_intent(current_beat_id: str, text: str) -> UserIntent:
    value = " ".join(str(text or "").casefold().split())
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _POSTPONE_PATTERNS):
        return "postpone"
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _REFUSE_PATTERNS):
        return "refuse"
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _ACCEPT_PATTERNS):
        return "accept"
    if "?" in value:
        return "question"
    if current_beat_id == "reencontro_fila_007":
        return "unclear"
    return "accept"


def _dialogue_anchor(script: PilotScript, beat_id: str) -> str:
    beat = script.beats.get(beat_id) or {}
    for unit in beat.get("units", []) or []:
        if isinstance(unit, dict) and unit.get("kind") == "dialogue":
            return str(unit.get("anchor") or unit.get("text") or "")
    return ""


def decide_supermarket_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Decide o pedido de ajuda e encaminha recusas ao pátio, não ao fim abrupto."""

    prepare_supermarket_script(script)
    current_id = state.node_id or script.first_beat_id
    intent = classify_supermarket_intent(current_id, user_text)

    if current_id == "reencontro_fila_007":
        if intent == "refuse":
            target_id = "yard_help_refused_001"
            if target_id not in script.beats:
                raise KeyError("Pátio de recusa não foi compilado: yard_help_refused_001")
            updated = PilotState.from_dict(state.to_dict())
            updated.node_id = target_id
            updated.finished = False
            updated.run_status = "active"
            updated.ending_code = ""
            updated.pending_next_beat_id = ""
            updated.interstitial_turns = 0
            updated.facts["_last_user_intent"] = intent
            updated.facts["_scene_location"] = "supermercado_caixa"
            updated.facts["help_to_car"] = "refused"
            return PilotTurn(
                engagement=classify_user_message(user_text),
                target_id=target_id,
                visible_fallback=_dialogue_anchor(script, target_id),
                system_prompt=(
                    "Você é Mary. O usuário recusou esperar no caixa. "
                    "Entre no pátio de encerramento: demonstre frustração leve, respeite a decisão, "
                    "não insista e deixe espaço para uma última resposta antes da despedida final."
                ),
                state=updated,
            )

        if intent in {"question", "postpone", "unclear"}:
            updated = PilotState.from_dict(state.to_dict())
            updated.node_id = current_id
            updated.pending_next_beat_id = ""
            updated.interstitial_turns = 0
            updated.facts["_last_user_intent"] = intent
            updated.facts["_scene_location"] = "supermercado_caixa"
            fallback = (
                "Claro... mas você consegue me esperar e ajudar até o carro?"
                if intent == "question"
                else "Sem pressa... você consegue me esperar e ajudar até o carro?"
            )
            return PilotTurn(
                engagement=classify_user_message(user_text),
                target_id=current_id,
                visible_fallback=fallback,
                system_prompt=(
                    "Você é Mary, ainda ao lado do caixa do supermercado. "
                    "Responda primeiro ao que o usuário disse, de forma curta e natural. "
                    "Depois confirme, sem pressão, se ele aceita esperar e ajudar até o carro. "
                    "Não diga que ele aceitou e não avance para o estacionamento.\n\n"
                    f"MENSAGEM DO USUÁRIO: {user_text}"
                ),
                state=updated,
            )

    turn = decide_turn(script, state, user_text)
    updated = PilotState.from_dict(turn.state.to_dict())
    updated.facts["_last_user_intent"] = intent
    updated.facts["_scene_location"] = _SUPERMARKET_LOCATIONS.get(
        turn.target_id,
        updated.facts.get("_scene_location", "supermercado_corredor"),
    )
    if current_id == "reencontro_fila_007" and intent == "accept":
        updated.facts["help_to_car"] = "accepted"
    return replace(turn, state=updated)
