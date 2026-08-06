from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import load_editorial_document
from services.editorial_runtime_types import EditorialState
from services.editorial_subjective_impressions import (
    render_subjective_impressions,
    update_subjective_impressions,
)


CARD_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"


def _document() -> dict:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    return load_editorial_document(package)


def test_card_declara_impressoes_separadas_de_fatos() -> None:
    document = _document()

    policy = document["subjective_impressions"]
    assert "respectful_and_safe" in policy["impressions"]
    assert "reciprocal_interest" in policy["impressions"]
    assert "user_fact_schema" in document


def test_interacao_respeitosa_fortalece_impressao_sem_criar_fato() -> None:
    document = _document()
    state = EditorialState(node_id="beat_001")

    updated, impressions = update_subjective_impressions(
        document,
        state,
        "Vamos com calma e respeito, sem pressa.",
        "engaged",
    )

    by_id = {item.impression_id: item for item in impressions}
    assert by_id["respectful_and_safe"].score >= 3
    assert by_id["respectful_and_safe"].band_id == "safe"
    assert "respectful_and_safe" not in updated.facts
    assert "_subjective_user_impressions_json" in updated.facts


def test_hostilidade_pode_reverter_impressao_anterior() -> None:
    document = _document()
    state = EditorialState(node_id="beat_001")
    state, _ = update_subjective_impressions(
        document,
        state,
        "Quero respeitar seus limites e ir com calma.",
        "engaged",
    )
    state.node_id = "beat_002"
    state.recent_engagement.append("engaged")

    state, impressions = update_subjective_impressions(
        document,
        state,
        "Agora a interação se torna hostil.",
        "hostile",
    )

    by_id = {item.impression_id: item for item in impressions}
    assert by_id["respectful_and_safe"].score < 0
    assert by_id["respectful_and_safe"].band_id in {"uncertain", "unsafe"}


def test_mesmo_turno_nao_aplica_evidencia_duas_vezes() -> None:
    document = _document()
    state = EditorialState(node_id="beat_001")

    state, first = update_subjective_impressions(
        document,
        state,
        "Eu tenho interesse e quero conhecer você melhor.",
        "engaged",
    )
    state, second = update_subjective_impressions(
        document,
        state,
        "Eu tenho interesse e quero conhecer você melhor.",
        "engaged",
    )

    first_by_id = {item.impression_id: item for item in first}
    second_by_id = {item.impression_id: item for item in second}
    assert first_by_id["reciprocal_interest"].score == second_by_id["reciprocal_interest"].score
    assert first_by_id["reciprocal_interest"].evidence_count == second_by_id["reciprocal_interest"].evidence_count


def test_renderizacao_deixa_claro_que_nao_sao_fatos() -> None:
    document = _document()
    state = EditorialState(node_id="beat_001")
    _, impressions = update_subjective_impressions(
        document,
        state,
        "Eu sinto medo, mas quero falar a verdade.",
        "engaged",
    )

    rendered = render_subjective_impressions(impressions)

    assert "percepções provisórias" in rendered
    assert "não fatos objetivos" in rendered
    assert "pontuações" in rendered
    assert "emotional_openness" not in rendered


def test_motor_e_reutilizavel_por_outro_card() -> None:
    document = {
        "subjective_impressions": {
            "minimum_evidence_count": 1,
            "impressions": {
                "reliable_colleague": {
                    "label": "Impressão profissional",
                    "evidence": [
                        {
                            "context_patterns": [r"\\bprazo\\b"],
                            "engagements": ["engaged"],
                            "delta": 3,
                            "evidence_label": "compromisso com prazo",
                        }
                    ],
                    "bands": [
                        {
                            "band_id": "reliable",
                            "min": 3,
                            "max": 10,
                            "interpretation": "Lia percebe o usuário como alguém potencialmente confiável no trabalho.",
                        }
                    ],
                }
            },
        }
    }
    state = EditorialState(node_id="work_001")

    _, impressions = update_subjective_impressions(
        document,
        state,
        "Eu entrego dentro do prazo.",
        "engaged",
    )

    assert [item.impression_id for item in impressions] == ["reliable_colleague"]
    assert impressions[0].band_id == "reliable"
