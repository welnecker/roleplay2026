from __future__ import annotations

import pytest

from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import decide_editorial_progression_turn


def _script(*, cycle: bool = False) -> PilotScript:
    final_target = "skip_a" if cycle else "final"
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "start",
                "beats": [
                    {
                        "beat_id": "start",
                        "units": [{"kind": "dialogue", "anchor": "Início."}],
                        "on_user": {"engaged": "skip_a"},
                    },
                    {
                        "beat_id": "skip_a",
                        "units": [{"kind": "dialogue", "anchor": "A."}],
                        "on_user": {"engaged": "skip_b"},
                        "skip_when_facts": {"fact_a": "skip_b"},
                    },
                    {
                        "beat_id": "skip_b",
                        "units": [{"kind": "dialogue", "anchor": "B."}],
                        "on_user": {"engaged": "final"},
                        "skip_when_facts": {"fact_b": final_target},
                    },
                    {
                        "beat_id": "final",
                        "units": [{"kind": "dialogue", "anchor": "Destino final."}],
                        "on_user": {"engaged": "final"},
                    },
                ],
                "endings": [],
            },
        }
    )


def _name_script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "thanks",
                "beats": [
                    {
                        "beat_id": "thanks",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Obrigado pela ajuda.",
                                "instruction": "Encerrar a ajuda sem perguntar o nome.",
                            }
                        ],
                        "on_user": {"engaged": "ask_name"},
                    },
                    {
                        "beat_id": "ask_name",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Eu nem sei seu nome.",
                            }
                        ],
                        "on_user": {"engaged": "next_request"},
                        "skip_when_facts": {"user_name": "next_request"},
                    },
                    {
                        "beat_id": "next_request",
                        "units": [
                            {
                                "kind": "dialogue",
                                "anchor": "Posso te pedir mais uma coisa?",
                            }
                        ],
                        "on_user": {"engaged": "next_request"},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_saltos_declarativos_encadeados_chegam_ao_primeiro_beat_nao_satisfeito() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        PilotState(node_id="start", facts={"fact_a": "1", "fact_b": "1"}),
        "Continue normalmente.",
    )

    assert turn.target_id == "final"
    assert turn.state.node_id == "final"
    assert turn.state.facts["_declared_skip_applied"] == "skip_a,skip_b"
    assert turn.visible_fallback == "Destino final."


def test_beat_de_nome_e_pulado_quando_nome_ja_foi_informado() -> None:
    turn = decide_editorial_progression_turn(
        _name_script(),
        PilotState(
            node_id="thanks",
            pending_next_beat_id="ask_name",
            facts={
                "user_name": "Janio",
                "_acknowledged_user_name": "Janio",
            },
        ),
        "Concordo, encontros casuais trazem emoção.",
    )

    assert turn.target_id == "next_request"
    assert turn.state.node_id == "next_request"
    assert turn.state.facts["user_name"] == "Janio"
    assert turn.state.facts["_declared_skip_applied"] == "ask_name"
    assert "nem sei seu nome" not in turn.visible_fallback.casefold()
    assert turn.visible_fallback == "Posso te pedir mais uma coisa?"


def test_ciclo_em_saltos_declarativos_falha_com_erro_editorial_claro() -> None:
    with pytest.raises(ValueError, match="Ciclo em skip_when_facts"):
        decide_editorial_progression_turn(
            _script(cycle=True),
            PilotState(node_id="start", facts={"fact_a": "1", "fact_b": "1"}),
            "Continue normalmente.",
        )
