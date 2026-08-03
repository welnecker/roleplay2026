from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import (
    compile_editorial_package,
    load_editorial_document,
)
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime import EditorialState, editorial_opening_text


ROOT = Path(__file__).resolve().parents[1]
CASADA_ROOT = ROOT / "installed_stories" / "casada_frustrada"
CAFE_ROOT = ROOT / "tests" / "fixtures" / "editorial_cards" / "encontro_no_cafe"


def test_dois_cards_editoriais_possuem_identidade_e_conteudo_isolados() -> None:
    casada = load_manifest(CASADA_ROOT / "manifest.yaml")
    cafe = load_manifest(CAFE_ROOT / "manifest.yaml")

    casada_document = load_editorial_document(casada)
    cafe_document = load_editorial_document(cafe)

    assert casada.manifest.package_id == "roleplay2026.casada_frustrada"
    assert cafe.manifest.package_id == "example.encontro_no_cafe"
    assert casada.root != cafe.root
    assert casada_document["character"]["name"] == "Mary"
    assert cafe_document["character"]["name"] == "Clara"
    assert "cafe_001" not in {
        beat["beat_id"]
        for block in casada_document["blocks"]
        for beat in block.get("beats", [])
    }
    assert "encontro_acidental_001" not in {
        beat["beat_id"]
        for block in cafe_document["blocks"]
        for beat in block.get("beats", [])
    }


def test_segundo_card_executa_no_mesmo_runtime_sem_importar_casada_frustrada() -> None:
    cafe = load_manifest(CAFE_ROOT / "manifest.yaml")
    script = compile_editorial_package(cafe)

    assert editorial_opening_text(script) == "Oi... esta cadeira está livre?"

    turn = decide_editorial_progression_turn(
        script,
        EditorialState(),
        "Claro, pode sentar.",
    )

    assert turn.target_id == "cafe_002"
    assert turn.finished is False
    assert turn.visible_fallback == "Obrigada. Eu sou Clara... e você?"
    assert script.beats["cafe_002"]["max_questions"] == 1
    assert script.beats["cafe_002"]["max_sentences"] == 2


def test_fixture_independente_nao_conhece_nomes_do_card_canonico() -> None:
    source = (CAFE_ROOT / "content" / "editorial.yaml").read_text(encoding="utf-8").casefold()
    manifest = (CAFE_ROOT / "manifest.yaml").read_text(encoding="utf-8").casefold()

    for forbidden in (
        "casada_frustrada",
        "mary",
        "alfredinho",
        "supermercado",
        "motel",
    ):
        assert forbidden not in source
        assert forbidden not in manifest
