from __future__ import annotations

from pathlib import Path

from services.editorial_followups import (
    editorial_followups_after,
    prepare_editorial_followups,
    state_after_editorial_followup,
)
from services.editorial_runtime_impl import PilotScript, PilotState


IMPLEMENTATION = Path("services/editorial_progression_impl.py")
REMOVED_SUPPORT = Path("services/editorial_progression_support.py")


def _script(name: str, target_id: str) -> PilotScript:
    return PilotScript(
        {
            "character": {"name": name},
            "engagement_policy": {"categories": {}},
            "organic_slack": {
                "state_updates": {
                    "automatic_followups": [
                        {
                            "target_id": target_id,
                            "facts": {"active_card": name},
                        }
                    ]
                }
            },
            "blocks": [
                {
                    "block_id": "main",
                    "beats": [
                        {
                            "beat_id": "beat_001",
                            "automatic_followups": [
                                {
                                    "target_id": target_id,
                                    "text": f"Ponte de {name}",
                                    "scene_location": "novo_local",
                                    "transition": {
                                        "time": "Depois",
                                        "location": "Outro lugar",
                                    },
                                }
                            ],
                        }
                    ],
                }
            ],
            "scene": {
                "first_beat_id": "beat_001",
                "beats": [
                    {
                        "beat_id": "beat_001",
                        "units": [{"kind": "dialogue", "anchor": "Início"}],
                        "on_user": {"engaged": target_id},
                    },
                    {
                        "beat_id": target_id,
                        "units": [{"kind": "dialogue", "anchor": "Destino"}],
                        "on_user": {"engaged": target_id},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_progressao_ativa_usa_modulo_proprio_de_pontes() -> None:
    source = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "from services.editorial_followups import" in source
    assert "editorial_progression_support" not in source


def test_pontes_ficam_associadas_ao_script_preparado() -> None:
    first = prepare_editorial_followups(_script("Clara", "clara_002"))
    first_mapping = first.editorial_followups

    second = prepare_editorial_followups(_script("Mary", "mary_002"))

    assert first_mapping["beat_001"][0]["target_id"] == "clara_002"
    assert second.editorial_followups["beat_001"][0]["target_id"] == "mary_002"
    assert editorial_followups_after("beat_001")[0]["target_id"] == "mary_002"


def test_ponte_aplica_local_e_fatos_declarados() -> None:
    script = prepare_editorial_followups(_script("Clara", "clara_002"))
    followup = script.editorial_followups["beat_001"][0]

    state = state_after_editorial_followup(PilotState(node_id="beat_001"), followup)

    assert state.node_id == "clara_002"
    assert state.facts["_scene_location"] == "novo_local"
    assert state.facts["active_card"] == "Clara"
    assert followup["text"].startswith("[DEPOIS — OUTRO LUGAR]")


def test_suporte_monolitico_de_pontes_foi_removido() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "prepare_editorial_followups(script)" in implementation
    assert not REMOVED_SUPPORT.exists()
    assert "_AUTOMATIC_FOLLOWUPS" not in implementation
