from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from packages.loader import load_manifest
from services.editorial_compiler import compile_editorial_document
from services.editorial_engine import (
    compile_transition_rules,
    evaluate_transition_rules,
)
from services.editorial_package_loader import load_editorial_yaml


FIXTURE_ROOT = Path("tests/fixtures/editorial_cards/grafo_condicional")
ENGINE_ROOT = Path("services/editorial_engine")


def test_card_independente_compila_transicoes_declarativas() -> None:
    package = load_manifest(FIXTURE_ROOT / "manifest.yaml")
    source = load_editorial_yaml(package.root / package.manifest.runtime.editorial.source)
    compiled = compile_editorial_document(source)

    beat = next(item for item in compiled["scene"]["beats"] if item["beat_id"] == "escolha_001")
    rules = beat["transition_rules"]

    assert [rule.transition_id for rule in rules] == [
        "aceitar",
        "recusar",
        "perguntar",
        "indefinido",
    ]
    assert source["blocks"][0]["beats"][0]["transitions"][0]["next"] == "aceito_001"


def test_engine_avanca_permanece_e_aplica_efeitos_declarados() -> None:
    package = load_manifest(FIXTURE_ROOT / "manifest.yaml")
    source = load_editorial_yaml(package.root / package.manifest.runtime.editorial.source)
    beat = source["blocks"][0]["beats"][0]
    rules = compile_transition_rules(beat)

    accepted = evaluate_transition_rules(
        rules,
        current_beat_id="escolha_001",
        intent="accept",
    )
    assert accepted is not None
    assert accepted.target_beat_id == "aceito_001"
    assert accepted.effects.facts["escolha"] == "aceita"
    assert accepted.effects.relationship["trust"] == 1

    question = evaluate_transition_rules(
        rules,
        current_beat_id="escolha_001",
        intent="question",
    )
    assert question is not None
    assert question.stay is True
    assert question.target_beat_id == "escolha_001"

    fallback = evaluate_transition_rules(
        rules,
        current_beat_id="escolha_001",
        intent="unclear",
    )
    assert fallback is not None
    assert fallback.transition_id == "indefinido"


def test_compilador_preserva_documento_fonte() -> None:
    package = load_manifest(FIXTURE_ROOT / "manifest.yaml")
    source = load_editorial_yaml(package.root / package.manifest.runtime.editorial.source)
    original = deepcopy(source)

    compile_editorial_document(source)

    assert source == original


def test_formatos_legados_convergem_para_o_mesmo_contrato() -> None:
    next_rules = compile_transition_rules({"next_beat_id": "beat_b"})
    assert len(next_rules) == 1
    assert next_rules[0].next_beat_id == "beat_b"
    assert next_rules[0].condition.engagement == "engaged"

    allowed_rules = compile_transition_rules(
        {"allowed_transitions": {"engaged": "beat_b", "hostile": "fim"}}
    )
    assert [(rule.condition.engagement, rule.next_beat_id) for rule in allowed_rules] == [
        ("engaged", "beat_b"),
        ("hostile", "fim"),
    ]


def test_engine_generico_nao_conhece_cards_ou_personagens() -> None:
    forbidden = (
        "casada_frustrada",
        "mary",
        "alfredinho",
        "janio",
        "supermercado",
        "reencontro_fila",
    )
    for path in ENGINE_ROOT.glob("*.py"):
        source = path.read_text(encoding="utf-8").casefold()
        for term in forbidden:
            assert term not in source, f"{term!r} encontrado em {path}"
