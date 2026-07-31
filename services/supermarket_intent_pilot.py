from __future__ import annotations

from dataclasses import replace
import re
from typing import Literal

from services.pilot_supermarket import (
    PilotScript,
    PilotState,
    PilotTurn,
    classify_user_message,
    decide_turn,
)

UserIntent = Literal["accept", "refuse", "postpone", "question", "unclear"]

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


def prepare_supermarket_script(script: PilotScript) -> PilotScript:
    """Aplica correções editoriais somente ao recorte do supermercado."""

    farewell = script.beats.get("encontro_acidental_004")
    if farewell:
        farewell["objective"] = (
            "Mary encerra o primeiro contato de forma simpática, sem verbalizar "
            "pensamentos íntimos nem antecipar interesse romântico."
        )
        units = farewell.get("units") or []
        for unit in units:
            if isinstance(unit, dict) and unit.get("kind") == "dialogue":
                unit["anchor"] = "Tchauzinho..."
                unit["instruction"] = (
                    "Despedida breve e natural. Não incluir pensamento, carência ou "
                    "comentário sobre a aparência do usuário."
                )

    request = script.beats.get("reencontro_fila_007")
    if request:
        request["objective"] = (
            "Mary pede ajuda até o carro e aguarda uma decisão explícita. "
            "Não presumir que o usuário aceitou."
        )

    carrying = script.beats.get("reencontro_fila_008")
    if carrying:
        carrying["objective"] = (
            "Após aceite confirmado, Mary segue com o usuário e o carrinho em direção ao carro."
        )

    arrival = script.beats.get("reencontro_fila_009")
    if arrival:
        arrival["objective"] = "Mary e o usuário chegam ao carro de Mary."

    script.endings.setdefault(
        "end_help_declined",
        {
            "ending_id": "end_help_declined",
            "run_status": "completed",
            "ending_code": "supermarket_help_declined",
            "mary_final_state": {"interest": 3, "desire": 2},
            "visible_delivery": {
                "kind": "dialogue",
                "delivery": "fixed",
                "text": "Tudo bem, sem problema. Obrigada assim mesmo... a gente se vê por aí.",
            },
            "memory_writes": [],
        },
    )
    return script


def classify_supermarket_intent(current_beat_id: str, text: str) -> UserIntent:
    value = " ".join(str(text or "").casefold().split())
    if "?" in value:
        return "question"
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _POSTPONE_PATTERNS):
        return "postpone"
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _REFUSE_PATTERNS):
        return "refuse"
    if any(re.search(pattern, value, flags=re.IGNORECASE) for pattern in _ACCEPT_PATTERNS):
        return "accept"
    if current_beat_id == "reencontro_fila_007":
        return "unclear"
    return "accept"


def decide_supermarket_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Decide o turno com consentimento explícito no pedido de ajuda até o carro."""

    prepare_supermarket_script(script)
    current_id = state.node_id or script.first_beat_id
    intent = classify_supermarket_intent(current_id, user_text)

    if current_id == "reencontro_fila_007":
        if intent == "refuse":
            updated = PilotState.from_dict(state.to_dict())
            updated.node_id = "end_help_declined"
            updated.finished = True
            updated.run_status = "completed"
            updated.ending_code = "supermarket_help_declined"
            updated.pending_next_beat_id = ""
            updated.interstitial_turns = 0
            updated.facts["_last_user_intent"] = intent
            updated.facts["_scene_location"] = "supermercado_caixa"
            updated.facts["help_to_car"] = "refused"
            return PilotTurn(
                engagement=classify_user_message(user_text),
                target_id="end_help_declined",
                visible_fallback="Tudo bem, sem problema. Obrigada assim mesmo... a gente se vê por aí.",
                system_prompt=(
                    "Você é Mary. O usuário recusou educadamente ajudar até o carro. "
                    "Respeite a recusa imediatamente, sem insistir, sem culpa e sem presumir deslocamento. "
                    "Faça uma despedida breve, simpática e sem pergunta."
                ),
                state=updated,
                finished=True,
                run_status="completed",
                ending_code="supermarket_help_declined",
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
                    "Não diga que ele aceitou, não avance para o estacionamento e não repita falas anteriores.\n\n"
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
