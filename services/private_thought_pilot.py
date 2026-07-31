from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from services.alfredinho_call_pilot import (
    apply_alfredinho_call_overrides,
    decide_alfredinho_call_turn,
    prepare_alfredinho_call_script,
)
from services.pilot_supermarket import PilotScript, PilotState, PilotTurn

PRIVATE_THOUGHT_VERSION = "1.0.4-private-thought"
_SAFE_THOUGHT = "Preciso encontrar um momento discreto para mandar mensagem ao Janio."
_SAFE_FALLBACK = (
    "[PENSAMENTO]\n"
    f"{_SAFE_THOUGHT}\n"
    "[/PENSAMENTO]\n\n"
    "Tá gelada sim, amor. Deixa eu guardar as compras e já levo uma para você."
)


def apply_private_thought_overrides(document: dict[str, Any]) -> dict[str, Any]:
    """Transforma retorno_casa_003 em pensamento privado, nunca em fala audível."""

    document = apply_alfredinho_call_overrides(document)
    document["script_version"] = PRIVATE_THOUGHT_VERSION
    for block in document.get("blocks", []):
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []):
            if not isinstance(beat, dict) or beat.get("beat_id") != "retorno_casa_003":
                continue
            beat["type"] = "thought"
            beat["required_movement"] = (
                "Mary responde normalmente a Alfredo e mantém qualquer intenção sobre Janio "
                "exclusivamente como pensamento interno marcado."
            )
            beat["canonical_line"] = _SAFE_THOUGHT
            beat["dramatic_direction"] = (
                "O nome Janio e qualquer desejo de mandar mensagem não podem aparecer na fala audível. "
                "Produzir no máximo um bloco de pensamento e uma fala curta para Alfredo."
            )
            beat["max_questions"] = 0
            beat["max_sentences"] = 3
    return document


def prepare_private_thought_script(script: PilotScript) -> PilotScript:
    script = prepare_alfredinho_call_script(script)
    beat = script.beats.get("retorno_casa_003")
    if not beat:
        return script
    beat["objective"] = (
        "Mary responde a Alfredo sem revelar Janio; a intenção de mandar mensagem fica apenas em pensamento."
    )
    for unit in beat.get("units") or []:
        if not isinstance(unit, dict):
            continue
        unit["kind"] = "thought"
        unit["anchor"] = _SAFE_THOUGHT
        unit["instruction"] = (
            "Manter esta informação exclusivamente entre [PENSAMENTO] e [/PENSAMENTO]."
        )
    return script


def decide_private_thought_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    prepare_private_thought_script(script)
    turn = decide_alfredinho_call_turn(script, state, user_text)
    if turn.target_id != "retorno_casa_003":
        return turn

    prompt = (
        "Você é Mary, já em casa e falando com Alfredo. Responda primeiro ao conteúdo dele de modo curto. "
        "Qualquer referência a Janio, atração, segredo ou intenção de mandar mensagem deve aparecer somente "
        "dentro de um único bloco [PENSAMENTO]...[/PENSAMENTO]. Depois do fechamento, fale apenas com Alfredo. "
        "Não repita o pensamento, não diga o nome Janio em voz alta e não acrescente outro parágrafo secreto.\n\n"
        f"FALA DE ALFREDO: {user_text}\n\n"
        f"FORMATO SEGURO DE REFERÊNCIA:\n{_SAFE_FALLBACK}"
    )
    return replace(turn, visible_fallback=_SAFE_FALLBACK, system_prompt=prompt)


def sanitize_private_thought_response(target_id: str, response: str, fallback: str) -> str:
    """Bloqueia vazamento de Janio para a fala audível no beat privado."""

    value = str(response or "").strip()
    if target_id != "retorno_casa_003" or not value:
        return value or fallback

    blocks = re.findall(
        r"\[PENSAMENTO\](.*?)\[/PENSAMENTO\]",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if len(blocks) != 1:
        return fallback

    audible = re.sub(
        r"\[PENSAMENTO\].*?\[/PENSAMENTO\]",
        "",
        value,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if re.search(
        r"\b(?:janio|jânio|mandar (?:um )?oi|mandar mensagem|que homem)\b",
        audible,
        re.IGNORECASE,
    ):
        return fallback
    return value
