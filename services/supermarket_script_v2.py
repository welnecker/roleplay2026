from __future__ import annotations

from dataclasses import replace
from typing import Any

from services.pilot_supermarket import PilotScript, PilotState, PilotTurn, classify_user_message
from services.private_thought_pilot import (
    apply_private_thought_overrides,
    clean_private_model_response,
    decide_private_thought_turn,
    prepare_private_thought_script,
)

SUPERMARKET_SCRIPT_V2_VERSION = "1.1.0-supermarket-playable"

CAR_BRIDGE = (
    "[PENSAMENTO]\n"
    "Caralho... nunca imaginei encontrar um cara tão legal e atraente no supermercado. "
    "Vou ligar pro meu marido e avisar que estou indo.\n"
    "[/PENSAMENTO]\n\n"
    "Alô... Alfredinho?"
)
HOME_BRIDGE = (
    "Cheguei, amor... tô exausta, ufa! Vou botar a cerveja pra gelar e guardar as compras. "
    "Não se preocupa... fica quietinho aí vendo seu jogo."
)
FIRST_PRIVATE_MESSAGE = (
    "[PENSAMENTO]\n"
    "Vou mandar só uma mensagem... não suporto essa espera.\n"
    "[/PENSAMENTO]\n\n"
    "Oi?"
)

_AUTOMATIC_FOLLOWUPS: dict[str, tuple[dict[str, str], ...]] = {
    "encontro_acidental_006": (
        {
            "target_id": "reencontro_fila_001",
            "text": "Olha você de novo... tá me seguindo, é? rsrsrs",
            "scene_location": "supermercado_fila",
        },
    ),
    "reencontro_fila_006": (
        {
            "target_id": "reencontro_fila_007",
            "text": (
                "Passou rapidinho pelo caixa, hein? Chegou minha vez. Dá pra você me esperar? "
                "Vou precisar de uma mãozinha até o carro."
            ),
            "scene_location": "supermercado_caixa",
        },
    ),
    "retorno_casa_001": (
        {
            "target_id": "retorno_casa_002",
            "text": HOME_BRIDGE,
            "scene_location": "casa_de_mary",
        },
        {
            "target_id": "mensagens_iniciais_001",
            "text": FIRST_PRIVATE_MESSAGE,
            "scene_location": "mensagem_privada_janio",
        },
    ),
}


def _beat(
    beat_id: str,
    order: int,
    line: str,
    next_id: str,
    *,
    questions: int = 1,
    sentences: int = 3,
) -> dict[str, Any]:
    return {
        "beat_id": beat_id,
        "order": order,
        "type": "dialogue",
        "required_movement": (
            "Mary abre somente este assunto, reage brevemente ao usuário e prepara uma resposta clara. "
            "Não antecipar o beat seguinte."
        ),
        "canonical_line": line,
        "dramatic_direction": (
            "Fala natural e jogável. Permitir no máximo uma reação orgânica curta antes de retomar o roteiro."
        ),
        "next_beat_id": next_id,
        "max_questions": questions,
        "max_sentences": sentences,
        "memory_writes": [],
        "allowed_transitions": {
            "engaged": next_id,
            "minimal": next_id,
            "dismissive": next_id,
            "nonsense": next_id,
            "mocking": "end_hostile",
            "hostile": "end_hostile",
        },
        "status": "active",
    }


def _replace_block_beats(block: dict[str, Any], beats: list[dict[str, Any]]) -> None:
    block["beats"] = beats
    block["max_movements_per_response"] = 1
    block["max_questions_per_response"] = 1
    rules = list(block.get("rules") or [])
    rules.extend(
        [
            "Cada beat abre um único assunto para o usuário responder.",
            "Mary pode reagir organicamente por no máximo um turno intermediário.",
            "Beats marcados como ponte automática não concedem turno ao usuário.",
            "Nunca misturar interlocutores ou movimentos diferentes na mesma mensagem.",
        ]
    )
    block["rules"] = list(dict.fromkeys(str(item) for item in rules if str(item).strip()))


def apply_supermarket_script_v2_overrides(document: dict[str, Any]) -> dict[str, Any]:
    """Publica o supermercado da planilha e as pontes sem voz de Alfredinho."""

    document = apply_private_thought_overrides(document)
    document["script_version"] = SUPERMARKET_SCRIPT_V2_VERSION

    blocks = {
        str(block.get("block_id", "")): block
        for block in document.get("blocks", [])
        if isinstance(block, dict)
    }

    encounter = blocks.get("encontro_acidental")
    if encounter is not None:
        _replace_block_beats(
            encounter,
            [
                _beat("encontro_acidental_001", 1, "Eita, caralho... desculpa!", "encontro_acidental_002", questions=0, sentences=2),
                _beat("encontro_acidental_002", 2, "Tem certeza que tá tudo bem? Não machucou?", "encontro_acidental_003", questions=2, sentences=2),
                _beat("encontro_acidental_003", 3, "Que alívio... pensei que tivesse machucado você. Tudo bem mesmo? Pode dizer se estiver doendo.", "encontro_acidental_004", questions=2, sentences=3),
                _beat("encontro_acidental_004", 4, "Humm... você por acaso mora no Plaza? Seu rosto não me é estranho...", "encontro_acidental_005", questions=1, sentences=2),
                _beat("encontro_acidental_005", 5, "Ah... que legal. Somos vizinhos, então?", "encontro_acidental_006", questions=1, sentences=2),
                _beat("encontro_acidental_006", 6, "Vou continuar minhas comprinhas... tchauzinho, vizinho.", "reencontro_fila_001", questions=0, sentences=2),
            ],
        )

    queue = blocks.get("reencontro_fila")
    if queue is not None:
        _replace_block_beats(
            queue,
            [
                _beat("reencontro_fila_001", 1, "Olha você de novo... tá me seguindo, é? rsrsrs", "reencontro_fila_002", questions=1),
                _beat("reencontro_fila_002", 2, "Parece que está recuperado do susto, vizinho...", "reencontro_fila_003", questions=0, sentences=2),
                _beat("reencontro_fila_003", 3, "O mercado tá cheio hoje. Essa fila do caixa tá desanimadora.", "reencontro_fila_004", questions=0, sentences=2),
                _beat("reencontro_fila_004", 4, "Tô olhando pro seu carrinho... cerveja, salgadinho e macarrão instantâneo. Isso é típico de solteiro ou passei longe?", "reencontro_fila_005", questions=1),
                _beat("reencontro_fila_005", 5, "Na minha casa é cerveja e futebol quase todo fim de semana. Já acostumei com essa rotina.", "reencontro_fila_006", questions=0, sentences=2),
                _beat("reencontro_fila_006", 6, "Olha, é sua vez no caixa. Passa suas compras. Depois sou eu.", "reencontro_fila_007", questions=0, sentences=2),
                _beat("reencontro_fila_007", 7, "Passou rapidinho pelo caixa, hein? Chegou minha vez. Dá pra você me esperar? Vou precisar de uma mãozinha até o carro.", "reencontro_fila_008", questions=1),
                _beat("reencontro_fila_008", 8, "Vizinho, você me espera? Vou precisar de uma ajudinha com tudo isso até o carro.", "reencontro_fila_009", questions=1),
                _beat("reencontro_fila_009", 9, "Prontinho. Olha o tamanho desse carrinho perto do seu! Você dá conta de empurrar?", "reencontro_fila_010", questions=1),
                _beat("reencontro_fila_010", 10, "Meu carro é aquele ali... vou abrir o porta-malas. Tá cansado?", "reencontro_fila_011", questions=1),
                _beat("reencontro_fila_011", 11, "Prontinho, né? Porta-malas cheio! Nem sei como te agradecer.", "reencontro_fila_012", questions=0),
                _beat("reencontro_fila_012", 12, "Você foi muito gentil, sabia? Eu nem sei seu nome... que distração a minha.", "reencontro_fila_013", questions=1),
                _beat("reencontro_fila_013", 13, "Foi muito legal te conhecer... posso te pedir só mais uma coisa? Prometo que vai ser a última.", "reencontro_fila_014", questions=1),
                _beat("reencontro_fila_014", 14, "Queria seu número. Pra saber se você não ficou com sequelas, sabe? Ai... que desculpa esfarrapada... desculpe, rsrsrs.", "reencontro_fila_015", questions=1),
                _beat("reencontro_fila_015", 15, "Anotado... posso te ligar, quem sabe, lá pelas oito?", "reencontro_fila_016", questions=1),
                _beat("reencontro_fila_016", 16, "Tá bom... então deixa eu ir. Meu telefone já tá vibrando aqui... Tchau... te ligo.", "retorno_casa_001", questions=0, sentences=3),
            ],
        )

    return document


def prepare_supermarket_script_v2(script: PilotScript) -> PilotScript:
    script = prepare_private_thought_script(script)
    for beat_id, beat in script.beats.items():
        if beat_id.startswith(("encontro_acidental_", "reencontro_fila_")):
            beat["objective"] = (
                "Abrir somente o assunto deste beat, reagir ao usuário de modo curto e não antecipar o próximo movimento."
            )
    return script


def decide_supermarket_script_v2_turn(
    script: PilotScript,
    state: PilotState,
    user_text: str,
) -> PilotTurn:
    """Executa a despedida e entrega as pontes automáticas ao runtime."""

    prepare_supermarket_script_v2(script)
    current_id = state.node_id or script.first_beat_id

    if current_id == "reencontro_fila_016":
        updated = PilotState.from_dict(state.to_dict())
        updated.node_id = "retorno_casa_001"
        updated.pending_next_beat_id = ""
        updated.interstitial_turns = 0
        updated.facts["_scene_location"] = "carro_mary_sozinha"
        updated.facts["_force_fixed_response"] = "true"
        updated.facts["_automatic_bridge"] = "true"
        updated.facts["alfredinho_has_voice"] = "false"
        return PilotTurn(
            engagement=classify_user_message(user_text),
            target_id="retorno_casa_001",
            visible_fallback=CAR_BRIDGE,
            system_prompt="Use exatamente a ponte editorial fornecida, sem acrescentar resposta de Alfredinho.",
            state=updated,
        )

    turn = decide_private_thought_turn(script, state, user_text)
    if turn.target_id in {"reencontro_fila_001", "reencontro_fila_007"}:
        # Esses beats são entregues automaticamente pelo runtime; se uma run antiga
        # cair neles diretamente, mantém a fala canônica sem quebrar a sequência.
        updated = PilotState.from_dict(turn.state.to_dict())
        updated.facts["_scene_location"] = (
            "supermercado_fila" if turn.target_id == "reencontro_fila_001" else "supermercado_caixa"
        )
        return replace(turn, state=updated)
    return turn


def automatic_followups_after(target_id: str) -> tuple[dict[str, str], ...]:
    return _AUTOMATIC_FOLLOWUPS.get(str(target_id), ())


def state_after_automatic_followup(state: PilotState, followup: dict[str, str]) -> PilotState:
    updated = PilotState.from_dict(state.to_dict())
    updated.node_id = str(followup["target_id"])
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0
    updated.facts["_scene_location"] = str(followup["scene_location"])
    updated.facts.pop("_force_fixed_response", None)
    if updated.node_id == "mensagens_iniciais_001":
        updated.facts["_automatic_bridge"] = "completed"
        updated.facts["active_interlocutor"] = "janio"
        updated.facts["alfredinho_has_voice"] = "false"
    return updated


def clean_supermarket_script_v2_response(response: str, fallback: str) -> str:
    return clean_private_model_response(response, fallback)
