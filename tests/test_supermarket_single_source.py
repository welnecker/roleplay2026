from __future__ import annotations

from pathlib import Path

import yaml

from services.pilot_supermarket import PilotScript
from services.supermarket_script_v2 import (
    automatic_followups_after,
    prepare_supermarket_script_v2,
)


SOURCE = (
    Path(__file__).resolve().parent.parent
    / "installed_stories"
    / "casada_frustrada"
    / "supermarket_pilot.yaml"
)


def load_script() -> PilotScript:
    raw = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    return prepare_supermarket_script_v2(PilotScript(raw))


def test_plaza_antecede_confirmacao_e_despedida() -> None:
    script = load_script()

    assert "mora no Plaza" in script.beats["encontro_acidental_004"]["canonical_line"]
    assert script.beats["encontro_acidental_004"]["next_beat_id"] == "encontro_acidental_005"
    assert "Somos vizinhos" in script.beats["encontro_acidental_005"]["canonical_line"]
    assert script.beats["encontro_acidental_005"]["next_beat_id"] == "encontro_acidental_006"
    assert "tchauzinho" in script.beats["encontro_acidental_006"]["canonical_line"].lower()


def test_preparacao_nao_reescreve_beats() -> None:
    raw = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    script = PilotScript(raw)
    before = script.beats["encontro_acidental_004"]["canonical_line"]

    result = prepare_supermarket_script_v2(script)

    assert result is script
    assert result.beats["encontro_acidental_004"]["canonical_line"] == before
    assert result.raw["script_version"] == "1.2.0-single-source"


def test_pontes_sao_lidas_do_roteiro() -> None:
    load_script()

    queue_bridge = automatic_followups_after("encontro_acidental_006")
    home_bridges = automatic_followups_after("reencontro_fila_016")

    assert queue_bridge[0]["target_id"] == "reencontro_fila_001"
    assert len(home_bridges) == 3
    assert [item["target_id"] for item in home_bridges] == [
        "retorno_casa_001",
        "retorno_casa_002",
        "mensagens_iniciais_001",
    ]
    assert "Alfredinho" in home_bridges[0]["text"]
    assert home_bridges[-1]["text"].endswith("Oi?")
