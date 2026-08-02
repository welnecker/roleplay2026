from __future__ import annotations

import pytest

from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_script_v2 import decide_supermarket_script_v2_turn


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


def test_saltos_declarativos_encadeados_chegam_ao_primeiro_beat_nao_satisfeito() -> None:
    turn = decide_supermarket_script_v2_turn(
        _script(),
        PilotState(node_id="start", facts={"fact_a": "1", "fact_b": "1"}),
        "Continue normalmente.",
    )

    assert turn.target_id == "final"
    assert turn.state.node_id == "final"
    assert turn.state.facts["_declared_skip_applied"] == "skip_a,skip_b"
    assert turn.visible_fallback == "Destino final."


def test_ciclo_em_saltos_declarativos_falha_com_erro_editorial_claro() -> None:
    with pytest.raises(ValueError, match="Ciclo em skip_when_facts"):
        decide_supermarket_script_v2_turn(
            _script(cycle=True),
            PilotState(node_id="start", facts={"fact_a": "1", "fact_b": "1"}),
            "Continue normalmente.",
        )
