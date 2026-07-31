from __future__ import annotations

from services.pilot_supermarket import PilotScript
from services.supermarket_runtime_authority import enforce_supermarket_runtime


def test_runtime_substitui_beat_antigo_da_planilha() -> None:
    script = PilotScript(
        {
            "scene": {
                "first_beat_id": "encontro_acidental_001",
                "beats": [
                    {
                        "beat_id": "encontro_acidental_001",
                        "canonical_line": "antigo 1",
                        "on_user": {"engaged": "encontro_acidental_002"},
                    },
                    {
                        "beat_id": "encontro_acidental_002",
                        "canonical_line": "antigo 2",
                        "on_user": {"engaged": "encontro_acidental_003"},
                    },
                    {
                        "beat_id": "encontro_acidental_003",
                        "canonical_line": "novo 3",
                        "on_user": {"engaged": "encontro_acidental_004"},
                    },
                    {
                        "beat_id": "encontro_acidental_004",
                        "canonical_line": "Tchauzinho...",
                        "on_user": {"engaged": "encontro_acidental_005"},
                    },
                    {
                        "beat_id": "encontro_acidental_005",
                        "canonical_line": "Somos vizinhos, então?",
                        "on_user": {"engaged": "encontro_acidental_006"},
                    },
                ],
                "endings": [],
            },
            "engagement_policy": {},
        }
    )

    result = enforce_supermarket_runtime(script)

    assert "mora no Plaza" in result.beats["encontro_acidental_004"]["canonical_line"]
    assert result.beats["encontro_acidental_004"]["next_beat_id"] == "encontro_acidental_005"
    assert "Somos vizinhos" in result.beats["encontro_acidental_005"]["canonical_line"]
    assert result.raw["script_version"] == "1.1.1-supermarket-runtime-authoritative"


def test_pergunta_do_plaza_sempre_antecede_confirmacao() -> None:
    script = PilotScript(
        {
            "scene": {
                "first_beat_id": "encontro_acidental_001",
                "beats": [{"beat_id": "encontro_acidental_001"}],
                "endings": [],
            },
            "engagement_policy": {},
        }
    )

    result = enforce_supermarket_runtime(script)

    assert result.beats["encontro_acidental_003"]["next_beat_id"] == "encontro_acidental_004"
    assert result.beats["encontro_acidental_004"]["next_beat_id"] == "encontro_acidental_005"
    assert result.beats["encontro_acidental_005"]["next_beat_id"] == "encontro_acidental_006"
