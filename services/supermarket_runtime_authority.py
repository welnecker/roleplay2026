from __future__ import annotations

from typing import Any

from services.pilot_supermarket import PilotScript


_SEQUENCE: tuple[tuple[str, str, str, int, int], ...] = (
    ("encontro_acidental_001", "Eita, caralho... desculpa!", "encontro_acidental_002", 0, 2),
    ("encontro_acidental_002", "Tem certeza que tá tudo bem? Não machucou?", "encontro_acidental_003", 2, 2),
    ("encontro_acidental_003", "Que alívio... pensei que tivesse machucado você. Tudo bem mesmo? Pode dizer se estiver doendo.", "encontro_acidental_004", 2, 3),
    ("encontro_acidental_004", "Humm... você por acaso mora no Plaza? Seu rosto não me é estranho...", "encontro_acidental_005", 1, 2),
    ("encontro_acidental_005", "Ah... que legal. Somos vizinhos, então?", "encontro_acidental_006", 1, 2),
    ("encontro_acidental_006", "Vou continuar minhas comprinhas... tchauzinho, vizinho.", "reencontro_fila_001", 0, 2),
    ("reencontro_fila_001", "Olha você de novo... tá me seguindo, é? rsrsrs", "reencontro_fila_002", 1, 3),
    ("reencontro_fila_002", "Parece que está recuperado do susto, vizinho...", "reencontro_fila_003", 0, 2),
    ("reencontro_fila_003", "O mercado tá cheio hoje. Essa fila do caixa tá desanimadora.", "reencontro_fila_004", 0, 2),
    ("reencontro_fila_004", "Tô olhando pro seu carrinho... cerveja, salgadinho e macarrão instantâneo. Isso é típico de solteiro ou passei longe?", "reencontro_fila_005", 1, 3),
    ("reencontro_fila_005", "Na minha casa é cerveja e futebol quase todo fim de semana. Já acostumei com essa rotina.", "reencontro_fila_006", 0, 2),
    ("reencontro_fila_006", "Olha, é sua vez no caixa. Passa suas compras. Depois sou eu.", "reencontro_fila_007", 0, 2),
    ("reencontro_fila_007", "Passou rapidinho pelo caixa, hein? Chegou minha vez. Dá pra você me esperar? Vou precisar de uma mãozinha até o carro.", "reencontro_fila_008", 1, 3),
    ("reencontro_fila_008", "Vizinho, você me espera? Vou precisar de uma ajudinha com tudo isso até o carro.", "reencontro_fila_009", 1, 2),
    ("reencontro_fila_009", "Prontinho. Olha o tamanho desse carrinho perto do seu! Você dá conta de empurrar?", "reencontro_fila_010", 1, 3),
    ("reencontro_fila_010", "Meu carro é aquele ali... vou abrir o porta-malas. Tá cansado?", "reencontro_fila_011", 1, 3),
    ("reencontro_fila_011", "Prontinho, né? Porta-malas cheio! Nem sei como te agradecer.", "reencontro_fila_012", 0, 3),
    ("reencontro_fila_012", "Você foi muito gentil, sabia? Eu nem sei seu nome... que distração a minha.", "reencontro_fila_013", 1, 3),
    ("reencontro_fila_013", "Foi muito legal te conhecer... posso te pedir só mais uma coisa? Prometo que vai ser a última.", "reencontro_fila_014", 1, 3),
    ("reencontro_fila_014", "Queria seu número. Pra saber se você não ficou com sequelas, sabe? Ai... que desculpa esfarrapada... desculpe, rsrsrs.", "reencontro_fila_015", 1, 4),
    ("reencontro_fila_015", "Anotado... posso te ligar, quem sabe, lá pelas oito?", "reencontro_fila_016", 1, 2),
    ("reencontro_fila_016", "Tá bom... então deixa eu ir. Meu telefone já tá vibrando aqui... Tchau... te ligo.", "retorno_casa_001", 0, 3),
)


def enforce_supermarket_runtime(script: PilotScript) -> PilotScript:
    """Sobrescreve no runtime qualquer linha editorial residual ou duplicada."""

    expected_ids = {beat_id for beat_id, *_ in _SEQUENCE}
    for order, (beat_id, line, next_id, questions, sentences) in enumerate(_SEQUENCE, start=1):
        beat: dict[str, Any] = script.beats.get(beat_id, {})
        beat.update(
            {
                "beat_id": beat_id,
                "order": order,
                "type": "dialogue",
                "canonical_line": line,
                "objective": "Abrir somente o assunto deste beat e não antecipar o próximo movimento.",
                "required_movement": "Mary reage brevemente e entrega somente o conteúdo deste beat.",
                "dramatic_direction": "Manter continuidade causal e nunca presumir informação ainda não fornecida.",
                "next_beat_id": next_id,
                "max_questions": questions,
                "max_sentences": sentences,
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
        )
        script.beats[beat_id] = beat

    # Garante que a pergunta sobre o Plaza sempre anteceda a confirmação de vizinhança.
    assert script.beats["encontro_acidental_003"]["next_beat_id"] == "encontro_acidental_004"
    assert "mora no Plaza" in script.beats["encontro_acidental_004"]["canonical_line"]
    assert script.beats["encontro_acidental_004"]["next_beat_id"] == "encontro_acidental_005"
    assert "Somos vizinhos" in script.beats["encontro_acidental_005"]["canonical_line"]

    script.raw["script_version"] = "1.1.1-supermarket-runtime-authoritative"
    script.raw["runtime_authoritative_beat_ids"] = sorted(expected_ids)
    return script
