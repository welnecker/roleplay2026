from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_memory_recall import (
    render_memory_recall_guidance,
    select_contextual_memories,
)
from services.editorial_package_loader import load_editorial_document


CARD_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"


def _document() -> dict:
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    return load_editorial_document(package)


def test_card_declara_politica_de_recuperacao_contextual() -> None:
    document = _document()
    policy = document["relationship_memory"]["recall_policy"]

    assert policy["max_memories_per_turn"] == 1
    assert policy["allow_background_fallback"] is False
    memory = next(
        item for item in document["memories"]
        if item["memory_id"] == "marital_frustration"
    )
    assert "casamento" in memory["recall_terms"]


def test_recupera_memoria_relacionada_ao_assunto_do_turno() -> None:
    document = _document()
    selected, facts = select_contextual_memories(
        document,
        [
            "marital_frustration",
            "user_as_awakening_possibility",
            "mary_tests_reciprocity_and_safety",
        ],
        {},
        "O usuário pergunta sobre o casamento, o marido e a rotina de Mary.",
    )

    assert selected == ["marital_frustration"]
    assert facts["_recalled_memory_ids"] == "marital_frustration"


def test_nao_injeta_memoria_quando_contexto_nao_tem_relacao() -> None:
    document = _document()
    selected, _ = select_contextual_memories(
        document,
        ["marital_frustration", "user_as_awakening_possibility"],
        {},
        "Mary pergunta qual produto o usuário procura no corredor do supermercado.",
    )

    assert selected == []


def test_cooldown_impede_repeticao_em_turnos_consecutivos() -> None:
    document = _document()
    selected, facts = select_contextual_memories(
        document,
        ["mary_tests_reciprocity_and_safety"],
        {},
        "A conversa trata de confiança, respeito e discrição.",
    )
    repeated, repeated_facts = select_contextual_memories(
        document,
        ["mary_tests_reciprocity_and_safety"],
        facts,
        "Novamente a conversa trata de confiança e respeito.",
    )

    assert selected == ["mary_tests_reciprocity_and_safety"]
    assert repeated == []
    assert repeated_facts["_recalled_memory_ids"] == ""


def test_memoria_resolvida_ou_esquecida_nao_e_recuperada() -> None:
    document = {
        "relationship_memory": {"recall_policy": {"max_memories_per_turn": 2}},
        "memories": {
            "resolved": {
                "summary": "Assunto encerrado.",
                "status": "resolved",
                "tags": ["assunto"],
            },
            "forgotten": {
                "summary": "Assunto esquecido.",
                "status": "forgotten",
                "tags": ["assunto"],
            },
        },
    }

    selected, _ = select_contextual_memories(
        document,
        ["resolved", "forgotten"],
        {},
        "O assunto voltou.",
    )

    assert selected == []


def test_orientacao_exige_callback_natural_sem_recitar_ficha() -> None:
    guidance = render_memory_recall_guidance(["memory_a"])

    assert "no máximo uma referência breve" in guidance
    assert "não recite a ficha" in guidance.casefold()
    assert "não diga que está lembrando" in guidance.casefold()


def test_seletor_e_reutilizavel_por_outro_card() -> None:
    document = {
        "relationship_memory": {
            "recall_policy": {
                "max_memories_per_turn": 1,
                "minimum_context_score": 1.0,
            }
        },
        "memories": {
            "coffee_meeting": {
                "summary": "Lia e o usuário se conheceram em uma cafeteria.",
                "importance": 7,
                "tags": ["café", "cafeteria"],
                "recall_terms": ["café", "cafeteria"],
            }
        },
    }

    selected, _ = select_contextual_memories(
        document,
        ["coffee_meeting"],
        {},
        "Lia pergunta se ele ainda gosta de café.",
    )

    assert selected == ["coffee_meeting"]
