from __future__ import annotations

from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_intent_pilot import (
    classify_supermarket_intent,
    decide_supermarket_turn,
    prepare_supermarket_script,
)


def _script() -> PilotScript:
    raw = {
        "engagement_policy": {"categories": {}},
        "scene": {
            "first_beat_id": "encontro_acidental_001",
            "beats": [
                {
                    "beat_id": "encontro_acidental_001",
                    "objective": "Pedir desculpas.",
                    "units": [{"kind": "dialogue", "anchor": "Desculpa!"}],
                    "on_user": {"engaged": "encontro_acidental_004"},
                },
                {
                    "beat_id": "encontro_acidental_004",
                    "objective": "Despedir.",
                    "units": [
                        {
                            "kind": "dialogue",
                            "anchor": "Tchauzinho... Hummm... que gato. Tô tão carente.",
                        }
                    ],
                    "on_user": {"engaged": "reencontro_fila_007"},
                },
                {
                    "beat_id": "reencontro_fila_007",
                    "objective": "Pedir ajuda.",
                    "units": [
                        {
                            "kind": "dialogue",
                            "anchor": "Você me espera? Acho que preciso de ajuda até o carro.",
                        }
                    ],
                    "on_user": {
                        "engaged": "reencontro_fila_008",
                        "minimal": "reencontro_fila_008",
                    },
                },
                {
                    "beat_id": "reencontro_fila_008",
                    "objective": "Ir ao carro.",
                    "units": [{"kind": "dialogue", "anchor": "Vamos até o carro."}],
                    "on_user": {"engaged": "reencontro_fila_009"},
                },
                {
                    "beat_id": "reencontro_fila_009",
                    "objective": "Chegar ao carro.",
                    "units": [{"kind": "dialogue", "anchor": "Chegamos."}],
                    "on_user": {"engaged": "reencontro_fila_009"},
                },
                {
                    "beat_id": "yard_help_refused_001",
                    "objective": "Respeitar a recusa e abrir a despedida.",
                    "units": [
                        {
                            "kind": "dialogue",
                            "anchor": "Ah... tudo bem. Achei que você pudesse esperar, mas eu entendo.",
                        }
                    ],
                    "on_user": {
                        "engaged": "yard_help_refused_002",
                        "minimal": "yard_help_refused_002",
                    },
                },
                {
                    "beat_id": "yard_help_refused_002",
                    "objective": "Encerrar organicamente.",
                    "units": [
                        {
                            "kind": "dialogue",
                            "anchor": "Relaxa... foi legal te conhecer mesmo assim.",
                        }
                    ],
                    "on_user": {"engaged": "end_help_declined"},
                },
            ],
            "endings": [
                {
                    "ending_id": "end_help_declined",
                    "run_status": "completed",
                    "ending_code": "supermarket_help_declined",
                    "visible_delivery": {
                        "kind": "dialogue",
                        "delivery": "fixed",
                        "text": "Tudo bem... a gente se vê por aí.",
                    },
                }
            ],
        },
    }
    return PilotScript(raw)


def test_remove_pensamento_obrigatorio_da_despedida() -> None:
    script = prepare_supermarket_script(_script())
    beat = script.beats["encontro_acidental_004"]

    assert beat["units"][0]["anchor"] == "Tchauzinho..."
    assert "carente" not in beat["units"][0]["anchor"].casefold()


def test_aceite_explicito_avanca_para_caminho_do_carro() -> None:
    turn = decide_supermarket_turn(
        _script(),
        PilotState(node_id="reencontro_fila_007"),
        "Claro, vou esperar e te ajudar.",
    )

    assert turn.target_id == "reencontro_fila_008"
    assert turn.state.facts["help_to_car"] == "accepted"
    assert turn.state.facts["_scene_location"] == "estacionamento_caminho"


def test_aceite_com_interrogacao_nao_repete_o_pedido() -> None:
    turn = decide_supermarket_turn(
        _script(),
        PilotState(node_id="reencontro_fila_007"),
        "Claro? vou te esperar na portaria..",
    )

    assert turn.target_id == "reencontro_fila_008"
    assert turn.state.facts["_last_user_intent"] == "accept"
    assert turn.state.facts["help_to_car"] == "accepted"
    assert turn.state.facts["_scene_location"] == "estacionamento_caminho"
    assert "consegue me esperar" not in turn.visible_fallback.casefold()


def test_recusa_entra_no_patio_sem_presumir_deslocamento() -> None:
    turn = decide_supermarket_turn(
        _script(),
        PilotState(node_id="reencontro_fila_007"),
        "Não posso ajudar agora, desculpa.",
    )

    assert turn.finished is False
    assert turn.run_status == "active"
    assert turn.ending_code == ""
    assert turn.target_id == "yard_help_refused_001"
    assert turn.state.facts["help_to_car"] == "refused"
    assert turn.state.facts["_scene_location"] == "supermercado_caixa"
    assert "eu entendo" in turn.visible_fallback.casefold()


def test_pergunta_nao_avanca_para_estacionamento() -> None:
    turn = decide_supermarket_turn(
        _script(),
        PilotState(node_id="reencontro_fila_007"),
        "Seu carro está muito longe?",
    )

    assert turn.target_id == "reencontro_fila_007"
    assert turn.finished is False
    assert turn.state.facts["_last_user_intent"] == "question"
    assert turn.state.facts["_scene_location"] == "supermercado_caixa"
    assert "não avance para o estacionamento" in turn.system_prompt


def test_resposta_vaga_pede_confirmacao() -> None:
    turn = decide_supermarket_turn(
        _script(),
        PilotState(node_id="reencontro_fila_007"),
        "Talvez...",
    )

    assert turn.target_id == "reencontro_fila_007"
    assert turn.state.facts["_last_user_intent"] == "unclear"
    assert "consegue me esperar" in turn.visible_fallback.casefold()


def test_classificador_separa_engajamento_de_intencao() -> None:
    assert classify_supermarket_intent("reencontro_fila_007", "Claro, eu ajudo") == "accept"
    assert classify_supermarket_intent("reencontro_fila_007", "Claro? vou te esperar na portaria") == "accept"
    assert classify_supermarket_intent("reencontro_fila_007", "Não consigo ajudar") == "refuse"
    assert classify_supermarket_intent("reencontro_fila_007", "Agora não, talvez depois") == "postpone"
    assert classify_supermarket_intent("reencontro_fila_007", "Onde está seu carro?") == "question"
