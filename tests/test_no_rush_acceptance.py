from __future__ import annotations

from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_intent import (
    classify_supermarket_intent,
    decide_supermarket_turn,
)


def _script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "reencontro_fila_007",
                "beats": [
                    {
                        "beat_id": "reencontro_fila_007",
                        "objective": "Pedir ajuda.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Você me espera? Preciso de ajuda até o carro.",
                            }
                        ],
                        "on_user": {
                            "engaged": "reencontro_fila_008",
                            "minimal": "reencontro_fila_008",
                        },
                    },
                    {
                        "beat_id": "reencontro_fila_008",
                        "objective": "Seguir com o carrinho.",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Prontinho. Você dá conta de empurrar?",
                            }
                        ],
                        "on_user": {"engaged": "reencontro_fila_008"},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_nao_estou_com_pressa_e_aceite() -> None:
    text = "Espero sim... não tô com pressa hoje."

    assert classify_supermarket_intent("reencontro_fila_007", text) == "accept"


def test_aceite_sem_pressa_nao_repete_o_pedido() -> None:
    turn = decide_supermarket_turn(
        _script(),
        PilotState(node_id="reencontro_fila_007"),
        "Espero sim... não tô com pressa hoje.",
    )

    assert turn.target_id == "reencontro_fila_008"
    assert turn.state.facts["_last_user_intent"] == "accept"
    assert turn.state.facts["help_to_car"] == "accepted"
    assert "você me espera" not in turn.visible_fallback.casefold()


def test_pressa_real_continua_sendo_adiamento() -> None:
    assert (
        classify_supermarket_intent(
            "reencontro_fila_007",
            "Agora não, tô com pressa. Talvez depois.",
        )
        == "postpone"
    )
