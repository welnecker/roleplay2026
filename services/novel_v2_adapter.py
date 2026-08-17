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
            instruction += f" Preserve apenas o sentido narrativo desta referência, sem copiá-la literalmente: {semantic_hint}"
        return NovelMovement(
            movement_id=movement_id,
            block_id=str(ending.get("block_id", "") or ""),
            instruction=instruction,
            dramatic_direction="Feche a cena com sensação de conclusão, sem comentários metalinguísticos.",
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
    direction = movement.dramatic_direction or "Interprete com naturalidade, ritmo e continuidade."
    return f"""MODO NOVELA INTERATIVA V2

Você interpreta {character_name} dentro de uma novela personalizada cujo protagonista é {protagonist}.
O roteiro controla O QUE acontece. Você controla COMO isso ganha vida.

MOVIMENTO ATUAL — execute somente este movimento:
{movement.instruction}

DIREÇÃO DRAMÁTICA:
{direction}

REGRAS DE EXECUÇÃO:
- Escreva uma cena viva, fluida e imersiva, sem mencionar roteiro, beat, movimento, prompt ou regras.
- Preserve a continuidade do histórico recebido.
- Pode narrar ações do protagonista quando o próprio movimento atual as pressupõe ou autoriza.
- Não peça confirmação para fazer o acontecimento previsto avançar.
- Hesitações previstas são recursos dramáticos; elas nunca cancelam a história.
- Não antecipe acontecimentos de movimentos futuros.
- Não reproduza falas ou pensamentos antigos como texto obrigatório; interprete o sentido do movimento.
- Use diálogo natural, gestos, ambiente, ritmo e reação emocional quando contribuírem para a cena.
- Evite enrolação e repetição. Faça cada avanço recompensar o clique em Avançar.
- Entregue apenas a cena final, sem explicações externas.
""".strip()


__all__ = [
    "NovelMovement",
    "build_novel_prompt",
    "movement_from_script",
    "next_movement_id",
]
