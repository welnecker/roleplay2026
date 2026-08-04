from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_compiler import compile_editorial_document
from services.editorial_package_loader import load_editorial_document
from services.editorial_progression import (
    editorial_followups_after,
    prepare_editorial_script,
)
from services.editorial_runtime import EditorialScript


PACKAGE_ROOT = (
    Path(__file__).resolve().parent.parent
    / "installed_stories"
    / "casada_frustrada"
)
FAREWELL_BEAT_ID = "encontro_acidental_despedida_001"


def load_document() -> dict:
    package = load_manifest(PACKAGE_ROOT / "manifest.yaml")
    return load_editorial_document(package)


def load_script() -> EditorialScript:
    compiled = compile_editorial_document(load_document())
    return prepare_editorial_script(EditorialScript(compiled))


def anchor(script: EditorialScript, beat_id: str) -> str:
    return str(script.beats[beat_id]["units"][0]["anchor"])


def test_plaza_antecede_confirmacao_apresentacao_e_despedida() -> None:
    script = load_script()

    assert "mora no Plaza" in anchor(script, "encontro_acidental_004")
    assert script.beats["encontro_acidental_004"]["on_user"]["engaged"] == "encontro_acidental_005"
    assert "Somos vizinhos" in anchor(script, "encontro_acidental_005")
    assert script.beats["encontro_acidental_005"]["on_user"]["engaged"] == "encontro_acidental_006"
    assert "eu sou a Mary" in anchor(script, "encontro_acidental_006")
    assert script.beats["encontro_acidental_006"]["on_user"]["engaged"] == FAREWELL_BEAT_ID
    assert "tchauzinho" in anchor(script, FAREWELL_BEAT_ID).lower()


def test_preparacao_nao_reescreve_beats() -> None:
    compiled = compile_editorial_document(load_document())
    script = EditorialScript(compiled)
    before = anchor(script, "encontro_acidental_004")

    result = prepare_editorial_script(script)

    assert result is script
    assert anchor(result, "encontro_acidental_004") == before
    assert result.raw["script_version"] == "1.2.0-single-source"


def test_pontes_sao_lidas_do_roteiro() -> None:
    load_script()

    queue_bridge = editorial_followups_after(FAREWELL_BEAT_ID)
    home_bridges = editorial_followups_after("reencontro_fila_016")

    assert queue_bridge[0]["target_id"] == "reencontro_fila_001"
    assert len(home_bridges) == 3
    assert [item["target_id"] for item in home_bridges] == [
        "retorno_casa_001",
        "retorno_casa_002",
        "mensagens_iniciais_001",
    ]
    assert "Alfredinho" in home_bridges[0]["text"]
    assert home_bridges[-1]["text"].endswith("Oi?")
