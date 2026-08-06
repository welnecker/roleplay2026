from __future__ import annotations

import json
from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import load_editorial_document
from services.editorial_user_facts import (
    extract_declared_user_facts,
    render_confirmed_user_facts,
    structured_user_facts,
)


CARD_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"


def _document() -> dict:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    return load_editorial_document(package)


def test_card_declara_esquema_de_fatos_independente_do_motor() -> None:
    document = _document()

    schema = document["user_fact_schema"]
    assert "user_relationship_status" in schema["facts"]
    assert "user_living_arrangement" in schema["facts"]
    assert "user_has_children" in schema["facts"]


def test_extrai_apenas_afirmacao_explicita() -> None:
    document = _document()

    vague = extract_declared_user_facts(
        document,
        "Às vezes a vida de solteiro parece mais simples.",
        {},
    )
    explicit = extract_declared_user_facts(
        document,
        "Eu sou solteiro e moro sozinho.",
        {},
    )

    assert "user_relationship_status" not in vague
    assert explicit["user_relationship_status"] == "single"
    assert explicit["user_living_arrangement"] == "lives_alone"


def test_correcao_substitui_valor_e_preserva_historico() -> None:
    document = _document()
    first = extract_declared_user_facts(document, "Sou casado.", {})
    corrected = extract_declared_user_facts(
        document,
        "Na verdade, estou separado.",
        first,
    )

    assert corrected["user_relationship_status"] == "separated"
    records = structured_user_facts(corrected)
    assert records["user_relationship_status"].value == "separated"
    assert records["user_relationship_status"].supersedes == "married"

    history = json.loads(corrected["_structured_user_fact_history_json"])
    assert history[-1]["value"] == "married"
    assert history[-1]["status"] == "replaced"


def test_baixa_confianca_nao_vira_fato() -> None:
    document = {
        "user_fact_schema": {
            "facts": {
                "user_job": {
                    "minimum_confidence": 0.9,
                    "extractors": [
                        {
                            "pattern": r"\btalvez eu seja professor\b",
                            "value": "teacher",
                            "confidence": 0.5,
                        }
                    ],
                }
            }
        }
    }

    facts = extract_declared_user_facts(document, "Talvez eu seja professor.", {})

    assert "user_job" not in facts
    assert "_structured_user_facts_json" not in facts


def test_prompt_expoe_somente_fato_ativo_sem_metadados_internos() -> None:
    document = _document()
    facts = extract_declared_user_facts(document, "Sou solteiro e não tenho filhos.", {})

    rendered = render_confirmed_user_facts(facts)

    assert "user_relationship_status: single" in rendered
    assert "user_has_children: false" in rendered
    assert "confidence" not in rendered
    assert "_structured_user_facts_json" not in rendered
    assert "não transforme impressão" in rendered.casefold()


def test_esquema_e_reutilizavel_por_outro_card() -> None:
    document = {
        "user_fact_schema": {
            "facts": {
                "user_likes_coffee": {
                    "minimum_confidence": 0.9,
                    "extractors": [
                        {
                            "pattern": r"\beu gosto de café\b",
                            "value": "true",
                            "confidence": 1.0,
                            "source": "explicit_self_report",
                        }
                    ],
                }
            }
        }
    }

    facts = extract_declared_user_facts(document, "Eu gosto de café.", {})

    assert facts["user_likes_coffee"] == "true"
