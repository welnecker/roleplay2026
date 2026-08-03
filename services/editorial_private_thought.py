from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from services.editorial_partner_call import (
    apply_alfredinho_call_overrides,
    decide_alfredinho_call_turn,
    prepare_alfredinho_call_script,
)
from services.editorial_runtime_impl import clean_model_response as base_clean_model_response
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn

PRIVATE_THOUGHT_VERSION = "1.0.5-home-clean-handoff"
_HOME_BEER_THOUGHT = "Vou entregar a cerveja e deixar o Alfredo se acomodar. Depois penso no Janio."
_HANDOFF_THOUGHT = (
    "Dei a cerveja... ele está satisfeito. Agora que estou sozinha, vou mandar uma mensagem para o Janio."
)
_HOME_FALLBACK = (
    "[PENSAMENTO]\n"
    f"{_HOME_BEER_THOUGHT}\n"
    "[/PENSAMENTO]\n\n"
    "Tá gelada sim, amor. Deixa eu guardar as compras e já levo uma para você."
)
_HANDOFF_FALLBACK = (
    "[PENSAMENTO]\n"
    f"{_HANDOFF_THOUGHT}\n"
    "[/PENSAMENTO]\n\n"
    "Você tá sozinho agora?"
)
_THOUGHT_BLOCK = re.compile(
    r"\[PENSAMENTO\](?P<thought>.*?)\[/PENSAMENTO\]",
    flags=re.IGNORECASE | re.DOTALL,
)


def apply_private_thought_overrides(document: dict[str, Any]) -> dict[str, Any]:
    """Separa a breve cena com Alfredo da primeira mensagem privada para Janio."""

    document = apply_alfredinho_call_overrides(document)
    document["script_version"] = PRIVATE_THOUGHT_VERSION
    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            if beat_id == "retorno_casa_003":
                beat["type"] = "thought"
                beat["required_movement"] = (
                    "Mary encerra a interação doméstica depois de responder brevemente a Alfredo. "
                    "Ela não abre outro assunto com o marido e prepara em pensamento a conversa privada com Janio."
                )
                beat["canonical_line"] = _HOME_BEER_THOUGHT
                beat["dramatic_direction"] = (
                    "No máximo uma resposta curta para Alfredo. Referências a Janio ficam exclusivamente "
                    "no pensamento. Não prolongar a conversa doméstica."
                )
                beat["max_questions"] = 0
                beat["max_sentences"] = 3
            elif beat_id == "mensagens_iniciais_001":
                beat["required_movement"] = (
                    "Com Alfredo já satisfeito e Mary sozinha, ela inicia uma conversa privada com Janio."
                )
                beat["canonical_line"] = "Você tá sozinho agora?"
                beat["dramatic_direction"] = (
                    "A primeira mensagem para Janio deve entrar limpa. Não falar com Alfredo, não entregar cerveja "
                    "e não repetir acontecimentos da cena doméstica na fala audível."
                )
                beat["max_questions"] = 1
                beat["max_sentences"] = 1
    return document


def prepare_private_thought_script(script: EditorialScript) -> EditorialScript:
    script = prepare_alfredinho_call_script(script)

    home_beat = script.beats.get("retorno_casa_003")
    if home_beat:
        home_beat["objective"] = (
            "Mary responde brevemente a Alfredo, encerra a atenção ao marido e prepara em pensamento "
            "a mensagem privada para Janio."
        )
        for unit in home_beat.get("units") or []:
            if not isinstance(unit, dict):
                continue
            unit["kind"] = "thought"
            unit["anchor"] = _HOME_BEER_THOUGHT
            unit["instruction"] = (
                "Manter Janio exclusivamente no pensamento e não abrir outro assunto com Alfredo."
            )

    first_message = script.beats.get("mensagens_iniciais_001")
    if first_message:
        first_message["objective"] = (
            "Mary já está sozinha e envia a primeira mensagem privada para Janio, sem resíduos da conversa com Alfredo."
        )
        for unit in first_message.get("units") or []:
            if isinstance(unit, dict) and unit.get("kind") == "dialogue":
                unit["anchor"] = "Você tá sozinho agora?"
                unit["instruction"] = (
                    "Enviar somente a primeira mensagem para Janio; não acrescentar fala dirigida a Alfredo."
                )
    return script


def decide_private_thought_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn:
    prepare_private_thought_script(script)
    current_id = state.node_id or script.first_beat_id
    turn = decide_alfredinho_call_turn(script, state, user_text)

    if turn.target_id == "retorno_casa_003":
        updated = EditorialState.from_dict(turn.state.to_dict())
        updated.facts["_scene_location"] = "casa_de_mary"
        updated.facts["home_husband_interactions"] = "1"
        prompt = (
            "Você é Mary, já em casa com Alfredo. Comece pelo pensamento privado. Depois responda ao que Alfredo "
            "acabou de dizer em uma única fala curta e encerre a atenção a ele. Não faça pergunta, não abra outro "
            "assunto e não prolongue a conversa doméstica. Qualquer referência a Janio deve ficar somente dentro "
            "de um único bloco [PENSAMENTO]...[/PENSAMENTO].\n\n"
            f"FALA DE ALFREDO: {user_text}\n\n"
            f"FORMATO SEGURO:\n{_HOME_FALLBACK}"
        )
        return replace(turn, visible_fallback=_HOME_FALLBACK, system_prompt=prompt, state=updated)

    if current_id == "retorno_casa_003" and turn.target_id == "mensagens_iniciais_001":
        updated = EditorialState.from_dict(turn.state.to_dict())
        updated.facts["_scene_location"] = "mensagem_privada_janio"
        updated.facts["home_scene_closed"] = "true"
        updated.facts["home_husband_interactions"] = "1"
        prompt = (
            "Você é Mary. A interação com Alfredo já terminou: a cerveja foi entregue, ele está satisfeito e Mary "
            "agora está sozinha. Comece por um único pensamento de transição. Depois envie somente a primeira mensagem "
            "privada para Janio: 'Você tá sozinho agora?'. Não fale com Alfredo, não diga que está entregando cerveja, "
            "não peça para ele esperar e não misture as duas cenas.\n\n"
            f"ÚLTIMA FALA DE ALFREDO: {user_text}\n\n"
            f"FORMATO SEGURO:\n{_HANDOFF_FALLBACK}"
        )
        return replace(turn, visible_fallback=_HANDOFF_FALLBACK, system_prompt=prompt, state=updated)

    return turn


def sanitize_private_thought_response(response: str, fallback: str) -> str:
    """Valida o pensamento, move-o para o início e impede mistura entre interlocutores."""

    value = str(response or "").strip()
    if not value:
        return fallback

    matches = list(_THOUGHT_BLOCK.finditer(value))
    if len(matches) != 1:
        return fallback

    match = matches[0]
    thought = str(match.group("thought") or "").strip()
    if not thought:
        return fallback

    before = value[: match.start()].strip()
    after = value[match.end() :].strip()
    audible_parts = [part for part in (before, after) if part]
    audible = "\n\n".join(audible_parts).strip()
    if not audible:
        return fallback

    if re.search(
        r"\b(?:janio|jânio|mandar (?:um )?oi|mandar mensagem|que homem)\b",
        audible,
        re.IGNORECASE,
    ):
        return fallback

    is_handoff = _HANDOFF_THOUGHT in str(fallback or "")
    if is_handoff:
        normalized = " ".join(audible.casefold().split())
        if normalized not in {"você tá sozinho agora?", "voce ta sozinho agora?"}:
            return fallback

    return f"[PENSAMENTO]\n{thought}\n[/PENSAMENTO]\n\n{audible}"


def clean_private_model_response(response: str, fallback: str) -> str:
    """Aplica a trava privada nos dois movimentos de encerramento da cena em casa."""

    cleaned = base_clean_model_response(response, fallback)
    fallback_value = str(fallback or "")
    if _HOME_BEER_THOUGHT not in fallback_value and _HANDOFF_THOUGHT not in fallback_value:
        return cleaned
    return sanitize_private_thought_response(cleaned, fallback)
