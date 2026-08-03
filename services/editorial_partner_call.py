from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from services.contact_exchange_pilot import (
    CONTACT_EXCHANGE_VERSION,
    apply_contact_exchange_overrides,
    decide_contact_exchange_turn,
    prepare_contact_exchange_script,
)
from services.pilot_supermarket import PilotScript, PilotState, PilotTurn, classify_user_message

ALFREDINHO_CALL_VERSION = "1.0.3-alfredinho-open-call"

_QUESTION_WORDS = re.compile(
    r"\b(?:quem|qual|quais|quando|onde|como|por que|porque|comprou|trouxe|pegou|lembrou|vai|vem|tem|tá|ta)\b",
    flags=re.IGNORECASE,
)
_EXPLICIT_CALL_END = re.compile(
    r"\b(?:até já|te espero|vem com cuidado|dirige com cuidado|vai com cuidado|"
    r"beijo|tchau|pode desligar|desliga então|falamos depois|depois a gente conversa)\b",
    flags=re.IGNORECASE,
)
_SHORT_ACK = re.compile(
    r"^(?:tá bom|ta bom|beleza|certo|ok|okay|tranquilo|combinado|pode deixar)[.!… ]*$",
    flags=re.IGNORECASE,
)


def apply_alfredinho_call_overrides(document: dict[str, Any]) -> dict[str, Any]:
    """Abre a ligação com Alfredinho sem antecipar a chegada em casa."""

    document = apply_contact_exchange_overrides(document)
    document["script_version"] = ALFREDINHO_CALL_VERSION
    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            if beat_id == "retorno_casa_001":
                beat["required_movement"] = (
                    "Mary conversa com Alfredinho pelo telefone enquanto está no carro. "
                    "Ela responde ao que ele disser e não anuncia chegada em casa enquanto a ligação estiver ativa."
                )
                beat["canonical_line"] = (
                    "Tô indo, amor. A fila demorou bem na minha vez, mas já saí do supermercado."
                )
                beat["dramatic_direction"] = (
                    "Responder diretamente a Alfredinho, esconder o motivo real do atraso e manter coerência: "
                    "Mary ainda está no carro. A conversa pode continuar ou terminar naturalmente."
                )
                beat["max_questions"] = 1
                beat["max_sentences"] = 4
            elif beat_id == "retorno_casa_002":
                beat["required_movement"] = (
                    "Somente depois de encerrada a ligação e concluído o deslocamento, Mary chega em casa."
                )
                beat["canonical_line"] = "Cheguei, amor. Quer uma cerveja?"
                beat["dramatic_direction"] = (
                    "Marcar claramente que Mary agora está em casa. Não repetir a desculpa da fila nem do trânsito."
                )
                beat["max_sentences"] = 3
    return document


def prepare_alfredinho_call_script(script: PilotScript) -> PilotScript:
    script = prepare_contact_exchange_script(script)
    call_beat = script.beats.get("retorno_casa_001")
    if call_beat:
        call_beat["objective"] = (
            "Mary está no carro, falando ao telefone com Alfredinho. Responder ao conteúdo dele, "
            "permitir que a conversa continue e não dizer que chegou em casa."
        )
        for unit in call_beat.get("units") or []:
            if isinstance(unit, dict) and unit.get("kind") == "dialogue":
                unit["anchor"] = (
                    "Tô indo, amor. A fila demorou bem na minha vez, mas já saí do supermercado."
                )
                unit["instruction"] = (
                    "Responder Alfredinho sem inventar chegada; manter Mary no carro enquanto a ligação estiver ativa."
                )

    arrival = script.beats.get("retorno_casa_002")
    if arrival:
        arrival["objective"] = (
            "A ligação terminou, Mary concluiu o deslocamento e agora chega em casa."
        )
        for unit in arrival.get("units") or []:
            if isinstance(unit, dict) and unit.get("kind") == "dialogue":
                unit["anchor"] = "Cheguei, amor. Quer uma cerveja?"
                unit["instruction"] = (
                    "Marcar chegada real à casa; não repetir desculpas já dadas ao telefone."
                )
    return script


def _is_question_or_continuation(text: str) -> bool:
    value = " ".join(str(text or "").casefold().split())
    if "?" in value:
        return True
    if _EXPLICIT_CALL_END.search(value):
        return False
    if _SHORT_ACK.fullmatch(value):
        return False
    return bool(_QUESTION_WORDS.search(value)) or len(value.split()) > 4


def _is_call_end(text: str) -> bool:
    value = " ".join(str(text or "").casefold().split())
    if "?" in value:
        return False
    return bool(_EXPLICIT_CALL_END.search(value) or _SHORT_ACK.fullmatch(value))


def decide_alfredinho_call_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Mantém a ligação aberta e separa seu encerramento da chegada em casa."""

    prepare_alfredinho_call_script(script)
    current_id = state.node_id or script.first_beat_id

    # Depois que Mary encerrou a ligação em um turno próprio, a próxima interação
    # libera normalmente o beat de chegada em casa.
    if current_id == "retorno_casa_001" and state.facts.get("alfredinho_call_closed") == "true":
        turn = decide_contact_exchange_turn(script, state, user_text)
        updated = PilotState.from_dict(turn.state.to_dict())
        updated.facts["_scene_location"] = "casa_de_mary"
        updated.facts["alfredinho_call_active"] = "false"
        return replace(turn, state=updated)

    if current_id == "retorno_casa_001":
        updated = PilotState.from_dict(state.to_dict())
        updated.node_id = current_id
        updated.pending_next_beat_id = ""
        updated.interstitial_turns = 0
        updated.facts["_scene_location"] = "carro_em_deslocamento"
        updated.facts["alfredinho_call_active"] = "true"

        if _is_call_end(user_text):
            updated.facts["alfredinho_call_closed"] = "true"
            fallback = "Pode deixar, amor. Já tô indo. Beijo."
            return PilotTurn(
                engagement=classify_user_message(user_text),
                target_id=current_id,
                visible_fallback=fallback,
                system_prompt=(
                    "Você é Mary, falando ao telefone com o marido enquanto está no carro. "
                    "Alfredinho encerrou ou sinalizou o fim da conversa. Responda com uma despedida breve e natural. "
                    "Não diga que chegou em casa, não ofereça cerveja e não abra outro assunto.\n\n"
                    f"FALA DE ALFREDINHO: {user_text}"
                ),
                state=updated,
            )

        if _is_question_or_continuation(user_text):
            updated.facts["alfredinho_call_closed"] = "false"
            fallback = "Tô indo, amor. Tá tudo certo por aqui."
            return PilotTurn(
                engagement=classify_user_message(user_text),
                target_id=current_id,
                visible_fallback=fallback,
                system_prompt=(
                    "Você é Mary, falando ao telefone com Alfredinho enquanto está no carro em deslocamento. "
                    "Responda diretamente ao que ele perguntou ou comentou. A ligação continua aberta. "
                    "Não diga 'cheguei', não coloque Mary dentro de casa, não ofereça cerveja e não repita mecanicamente "
                    "a desculpa da fila. Não invente que esqueceu compras; use apenas fatos confirmados.\n\n"
                    f"FALA DE ALFREDINHO: {user_text}"
                ),
                state=updated,
            )

    turn = decide_contact_exchange_turn(script, state, user_text)
    if turn.target_id != "retorno_casa_001":
        return turn

    updated = PilotState.from_dict(turn.state.to_dict())
    updated.facts["_scene_location"] = "carro_em_deslocamento"
    updated.facts["alfredinho_call_active"] = "true"
    updated.facts["alfredinho_call_closed"] = "false"
    return replace(turn, state=updated)
