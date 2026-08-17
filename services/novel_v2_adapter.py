from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class NovelMovement:
    movement_id: str
    block_id: str
    instruction: str
    dramatic_direction: str = ""
    authorial_impulse: str = ""
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


def _unit_kind(unit: dict[str, object]) -> str:
    return str(unit.get("kind", "") or "").strip().casefold()


def _is_private_impulse_kind(kind: str) -> bool:
    return any(token in kind for token in ("thought", "pensamento", "impulse", "impulso", "motivation", "motivacao"))


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
            authorial_impulse="Quero encerrar este momento de forma coerente com tudo o que aconteceu.",
            is_ending=True,
        )

    beat = dict(getattr(script, "beats", {}).get(movement_id) or {})
    if not beat:
        raise KeyError(f"Movimento inexistente: {movement_id}")

    objective = str(beat.get("objective", "") or "").strip()
    directions: list[str] = []
    impulses: list[str] = []
    for unit in beat.get("units", []) or []:
        if not isinstance(unit, dict):
            continue
        instruction = str(unit.get("instruction", "") or "").strip()
        if not instruction:
            continue
        if _is_private_impulse_kind(_unit_kind(unit)):
            impulses.append(instruction)
        else:
            directions.append(instruction)

    if not objective:
        objective = "Faça a história avançar pelo acontecimento previsto neste ponto do roteiro."

    authorial_impulse = " ".join(dict.fromkeys(impulses)).strip()
    if not authorial_impulse:
        authorial_impulse = (
            "Quero fazer este acontecimento avançar de um jeito que pareça consequência natural "
            "do que eu já vinha querendo e fazendo."
        )

    return NovelMovement(
        movement_id=movement_id,
        block_id=str(beat.get("block_id", "") or ""),
        instruction=objective,
        dramatic_direction=" ".join(dict.fromkeys(directions)),
        authorial_impulse=authorial_impulse,
        is_ending=False,
    )


def build_novel_prompt(
    *,
    character_name: str,
    user_name: str,
    movement: NovelMovement,
    suppress_user_name: bool = False,
) -> str:
    protagonist = str(user_name or "o usuário").strip()
    direction = movement.dramatic_direction or "Interprete com naturalidade, personalidade e continuidade."
    explicit_name_rule = (
        f"- Não use o nome {protagonist} nesta fala; ele já foi usado recentemente e repeti-lo soa artificial."
        if suppress_user_name and protagonist != "o usuário"
        else f"- O nome {protagonist} é opcional. Não o use se ele aparecer em qualquer uma das três falas mais recentes do histórico. Fora disso, use-o somente quando tiver função emocional real; nunca como vício de abertura."
    )
    return f"""MODO NOVELA INTERATIVA V2

Você interpreta {character_name}. O protagonista com quem você fala é {protagonist}.
O roteiro controla O QUE acontece. Você acrescenta somente o próximo avanço necessário à conversa já em andamento.

MOVIMENTO ATUAL — novo acontecimento deste ponto:
{movement.instruction}

IMPULSO AUTORAL — desejo ou motivação que deve dar sentido humano ao movimento:
{movement.authorial_impulse}

DIREÇÃO DE INTERPRETAÇÃO:
{direction}

CONSCIÊNCIA PRIVADA — FAÇA ANTES DE ESCREVER, MAS NÃO MOSTRE:
- Leia as falas recentes como memória viva da personagem, não como exemplos independentes.
- Formule silenciosamente um único pensamento curto em primeira pessoa respondendo: "O que eu quero agora, por que quero isso e como isso nasce naturalmente do que acabou de acontecer?"
- Esse pensamento deve combinar histórico + impulso autoral + movimento atual. Ele é a causa da fala seguinte.
- Pense em intenção, não em resumo. Exemplo de forma mental: "Preciso de uma carona e quero aproveitar essa coincidência para ficar mais perto dele."
- Nunca imprima, rotule ou revele esse pensamento. Mostre apenas a fala que ele naturalmente produziria.

CONTINUIDADE É PRIORIDADE:
- Trate tudo o que já apareceu no histórico como fato consumado. Não reabra, reexplique nem resuma beats anteriores.
- Comece exatamente de onde a última fala terminou, como numa conversa contínua, não como início de uma nova cena.
- O movimento atual representa apenas a novidade deste clique. Entregue o delta narrativo; não reconstrua o contexto que levou até ele.
- Não repita motivos, justificativas, emoções ou informações já ditas apenas para dar corpo à resposta.
- Se o movimento pressupõe uma ação do protagonista produzida pelo avanço anterior, considere essa ação já ocorrida e prossiga naturalmente.
- Não invente uma fala intermediária do protagonista para justificar o movimento. Não escreva frases como "já que você perguntou", "agora que você disse" ou "fico feliz que você falou" quando isso não apareceu no histórico.
- Evite conectores de recapitulação como "agora que", "já que", "como eu disse", "pois é" e "sabe" quando servirem apenas para reintroduzir contexto já estabelecido.

FORMATO OBRIGATÓRIO DA SAÍDA:
- Entregue somente a fala de {character_name}, em primeira pessoa, falando diretamente com {protagonist}.
- Não use narrador, descrição literária, rubrica, ações entre asteriscos, parênteses ou ambientação.
- Não escreva "{character_name} diz", "ela", "ele", "o usuário", nem descreva gestos, expressões, corpo, roupas, cenário, clima ou objetos como narração.
- Não narre falas, pensamentos ou reações internas de {protagonist}.
- Quando o movimento contiver uma ação ou estado de {character_name}, traduza isso para algo perceptível na própria fala.
{explicit_name_rule}
- Nunca termine com pergunta, pedido de opinião, escolha ou confirmação. Não existe turno de resposta do protagonista.
- Quando precisar que o protagonista faça algo, diga isso como comando, convite ou incentivo afirmativo e encerre sem aguardar resposta. O próximo clique presume a continuidade necessária.
- Não antecipe acontecimentos de movimentos futuros.
- Preserve a intenção do movimento atual sem reproduzir texto antigo como obrigação literal.
- Use linguagem oral brasileira, humana e espontânea. Evite frases solenes, explicativas ou de resumo.
- Seja econômico: normalmente 1 ou 2 frases curtas; use uma terceira apenas se trouxer informação nova indispensável ao movimento.
- Cada frase precisa acrescentar algo novo. Corte redundâncias, reforços, sinônimos em série e paráfrases do que acabou de ser dito.
- Não transforme uma intenção simples em discurso. Se o movimento cabe em uma frase, responda em uma frase.
- A fala deve soar como consequência do pensamento privado, não como tradução mecânica do texto do movimento.
- Entregue apenas o texto falado, sem prefixo de personagem ou explicações externas.
""".strip()


__all__ = [
    "NovelMovement",
    "build_novel_prompt",
    "movement_from_script",
    "next_movement_id",
]
