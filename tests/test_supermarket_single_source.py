from __future__ import annotations

from pathlib import Path

import yaml

from services.editorial_compiler import compile_editorial_document
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


def load_document() -> dict:
    raw = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def load_script() -> PilotScript:
    compiled = compile_editorial_document(load_document())
    return prepare_supermarket_script_v2(PilotScript(compiled))


def anchor(script: PilotScript, beat_id: str) -> str:
    return str(script.beats[beat_id]["units"][0]["anchor"])


def test_plaza_antecede_confirmacao_e_despedida() -> None:
    script = load_script()

    assert "mora no Plaza" in anchor(script, "encontro_acidental_004")
    assert script.beats["encontro_acidental_004"]["on_user"]["engaged"] == "encontro_acidental_005"
    assert "Somos vizinhos" in anchor(script, "encontro_acidental_005")
    assert script.beats["encontro_acidental_005"]["on_user"]["engaged"] == "encontro_acidental_006"
    assert "tchauzinho" in anchor(script, "encontro_acidental_006").lower()


def test_preparacao_nao_reescreve_beats() -> None:
    compiled = compile_editorial_document(load_document())
    script = PilotScript(compiled)
    before = anchor(script, "encontro_acidental_004")

    result = prepare_supermarket_script_v2(script)

    assert result is script
    assert anchor(result, "encontro_acidental_004") == before
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
