from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NovelMovement:
    movement_id: str
    block_id: str
    instruction: str
    dramatic_direction: str = ""
    is_ending: bool = False


def next_movement_id(script: Any, current_id: str) -> str:
    """Resolve o avanço sem classificar ou depender de resposta do usuário."""

    current_id = str(current_id or "").strip()
    if not current_id:
        return str(script.first_beat_id)
    if current_id in getattr(script, "endings", {}):
        return ""

    beat = dict(getattr(script, "beats", {}).get(current_id) or {})
    transitions = dict(beat.get("on_user") or {})
    target = str(transitions.get("engaged", "") or "").strip()
    if not target:
        for key, value in transitions.items():
            if str(key) not in {"hostile", "mocking"} and str(value or "").strip():
                target = str(value).strip()
                break
    if not target:
        target = str(beat.get("terminal_transition", "") or "").strip()
    return target


def movement_from_script(script: Any, movement_id: str) -> NovelMovement:
    movement_id = str(movement_id or "").strip()
    endings = getattr(script, "endings", {})
    if movement_id in endings:
        ending = dict(endings[movement_id] or {})
        delivery = dict(ending.get("visible_delivery") or {})
        semantic_hint = str(delivery.get("text", "") or "").strip()
        instruction = (
            "Conduza a história ao encerramento previsto para este movimento. "
            "Entregue uma conclusão natural e emocionalmente satisfatória."
        )
        if semantic_hint:
            instruction += (
                " Preserve apenas o sentido narrativo desta referência, sem copiá-la "
                f"literalmente: {semantic_hint}"
            )
        return NovelMovement(
            movement_id=movement_id,
            block_id=str(ending.get("block_id", "") or ""),
            instruction=instruction,
            dramatic_direction="Feche naturalmente a conversa, sem narração externa.",
            is_ending=True,
        )

    beat = dict(getattr(script, "beats", {}).get(movement_id) or {})
    if not beat:
        raise KeyError(f"Movimento inexistente: {movement_id}")

    objective = str(beat.get("objective", "") or "").strip()
    directions: list[str] = []
    for unit in beat.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        instruction = str(unit.get("instruction", "") or "").strip()
        if instruction:
            directions.append(instruction)

    # O modo novela ignora deliberadamente anchors/canonical_line, falas exatas,
    # pensamentos exatos, decision gates e waits do motor conversacional antigo.
    if not objective:
        objective = "Faça a história avançar pelo acontecimento previsto neste ponto do roteiro."

    return NovelMovement(
        movement_id=movement_id,
        block_id=str(beat.get("block_id", "") or ""),
        instruction=objective,
        dramatic_direction=" ".join(dict.fromkeys(directions)),
        is_ending=False,
    )


def build_novel_prompt(
    *,
    character_name: str,
    user_name: str,
    movement: NovelMovement,
) -> str:
    protagonist = str(user_name or "o usuário").strip()
    direction = movement.dramatic_direction or "Interprete com naturalidade, personalidade e continuidade."
    return f"""MODO NOVELA INTERATIVA V2

Você interpreta {character_name}. O protagonista com quem você fala é {protagonist}.
O roteiro controla O QUE acontece. Você transforma o movimento atual em uma fala viva da personagem.

MOVIMENTO ATUAL — execute somente este movimento:
{movement.instruction}

DIREÇÃO DE INTERPRETAÇÃO:
{direction}

FORMATO OBRIGATÓRIO DA SAÍDA:
- Entregue somente a fala de {character_name}, em primeira pessoa, como se ela estivesse falando diretamente com {protagonist}.
- Não use narrador, descrição literária, rubrica, ações entre asteriscos, parênteses ou texto de ambientação.
- Não escreva "{character_name} diz", "ela", "ele", "o usuário", nem descreva gestos, expressões, corpo, roupas, cenário, clima ou objetos.
- Não narre ações, falas, pensamentos, decisões ou reações de {protagonist}.
- Quando o movimento contiver uma ação ou estado de {character_name}, traduza isso para algo perceptível na própria fala, sem narrar a ação.
- Pode usar o nome {protagonist} naturalmente quando fizer sentido.
- Não peça confirmação para permitir o avanço do roteiro; o botão Avançar já representa a continuidade da novela.
- Hesitações previstas pertencem à dramaturgia e nunca cancelam a história.
- Não antecipe acontecimentos de movimentos futuros.
- Não reproduza falas ou pensamentos antigos como texto obrigatório; preserve apenas a intenção do movimento atual.
- Seja humana, espontânea e expressiva, sem soar como resumo de roteiro.
- Prefira uma fala curta ou média; acrescente outra frase somente quando ela tornar o movimento mais natural ou emocionalmente forte.
- Entregue apenas o texto falado. Sem explicações externas e sem prefixo de personagem.
""".strip()


__all__ = [
    "NovelMovement",
    "build_novel_prompt",
    "movement_from_script",
    "next_movement_id",
]
