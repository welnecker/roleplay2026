from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from services.pilot_supermarket import PilotScript, PilotState, PilotTurn, classify_user_message
from services.supermarket_intent_pilot import (
    apply_supermarket_document_overrides,
    decide_supermarket_turn,
    prepare_supermarket_script,
)

MARY_PHONE_NUMBER = "99982-6413"
CONTACT_EXCHANGE_VERSION = "1.0.2-contact-exchange"
_NUMBER_REQUEST = re.compile(
    r"\b(?:pode dizer|fala(?: o)? número|qual(?: é)?(?: o)? seu número|vou anotar|me passa(?: o)? número)\b",
    flags=re.IGNORECASE,
)


def apply_contact_exchange_overrides(document: dict[str, Any]) -> dict[str, Any]:
    """Completa a troca de contatos sem alterar a sequência posterior."""

    document = apply_supermarket_document_overrides(document)
    document["script_version"] = CONTACT_EXCHANGE_VERSION
    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict) or beat.get("beat_id") != "reencontro_fila_014":
                continue
            beat["required_movement"] = (
                "Mary confirma o recebimento do número do usuário e fornece imediatamente "
                "o próprio número antes de qualquer despedida."
            )
            beat["canonical_line"] = (
                f"Olha... esse número vai me trazer sorte. O meu é {MARY_PHONE_NUMBER}. Salva aí."
            )
            beat["dramatic_direction"] = (
                "Responder brevemente à preocupação do usuário e entregar o número completo. "
                "Não apenas prometer que irá fornecê-lo."
            )
            beat["max_questions"] = 0
            beat["max_sentences"] = 3
    return document


def prepare_contact_exchange_script(script: PilotScript) -> PilotScript:
    script = prepare_supermarket_script(script)
    beat = script.beats.get("reencontro_fila_014")
    if not beat:
        return script
    beat["objective"] = (
        "Mary confirma o número recebido e fornece imediatamente o próprio número."
    )
    for unit in beat.get("units") or []:
        if isinstance(unit, dict) and unit.get("kind") == "dialogue":
            unit["anchor"] = (
                f"Olha... esse número vai me trazer sorte. O meu é {MARY_PHONE_NUMBER}. Salva aí."
            )
            unit["instruction"] = (
                "Entregar o número completo antes da despedida; não deixar promessa pendente."
            )
    return script


def decide_contact_exchange_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Preenche o número prometido caso uma run antiga ainda pare no beat 014."""

    prepare_contact_exchange_script(script)
    current_id = state.node_id or script.first_beat_id
    if current_id == "reencontro_fila_014" and _NUMBER_REQUEST.search(str(user_text or "")):
        updated = PilotState.from_dict(state.to_dict())
        updated.node_id = "reencontro_fila_014"
        updated.pending_next_beat_id = ""
        updated.interstitial_turns = 0
        updated.facts["mary_phone_shared"] = "true"
        updated.facts["_last_user_intent"] = "request_contact_detail"
        fallback = f"Claro. O meu é {MARY_PHONE_NUMBER}. Salva aí."
        return PilotTurn(
            engagement=classify_user_message(user_text),
            target_id="reencontro_fila_014",
            visible_fallback=fallback,
            system_prompt=(
                "Você é Mary. O usuário pediu o número que você acabou de prometer. "
                f"Forneça exatamente {MARY_PHONE_NUMBER}, de forma direta e natural. "
                "Não se despeça ainda, não faça outra pergunta e não invente outro número.\n\n"
                f"MENSAGEM DO USUÁRIO: {user_text}"
            ),
            state=updated,
        )

    turn = decide_supermarket_turn(script, state, user_text)
    if turn.target_id != "reencontro_fila_014":
        return turn
    updated = PilotState.from_dict(turn.state.to_dict())
    updated.facts["mary_phone_shared"] = "true"
    return replace(turn, state=updated)
