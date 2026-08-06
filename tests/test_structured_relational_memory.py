from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState
from services.narrative_context import build_narrative_context, memory_catalog


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_card_declares_reusable_relationship_profile() -> None:
    document = load_source_document()
    profile = document["relationship_memory"]

    assert profile["initial_memory_ids"] == [
        "marital_frustration",
        "user_as_awakening_possibility",
        "mary_tests_reciprocity_and_safety",
    ]
    assert "casamento frustrante" in profile["premise"]
    assert "possibilidade concreta de libertação" in profile["character_view_of_user"]


def test_memory_catalog_preserves_structured_metadata() -> None:
    catalog = memory_catalog(load_source_document())
    awakening = catalog["user_as_awakening_possibility"]

    assert awakening.category == "relational_turning_point"
    assert awakening.subject == "relationship"
    assert awakening.importance == 10
    assert awakening.emotional_weight == 10
    assert awakening.relationship_relevance == 10
    assert awakening.confidence == 0.9
    assert awakening.sensitivity == "intimate"
    assert awakening.recall_cooldown_turns == 6
    assert awakening.tags == ("desejo", "libertação", "possibilidade")
    assert awakening.recall_priority > 8


def test_relational_context_explains_mary_without_making_user_a_savior() -> None:
    document = load_source_document()
    context = build_narrative_context(
        document,
        document["relationship_memory"]["initial_memory_ids"],
        {"user_name": "Janio"},
    )

    assert "EIXO RELACIONAL DE MARY" in context
    assert "desejo foram abafados" in context
    assert "Janio" in context
    assert "sem tomar essa possibilidade como garantia" in context
    assert "não transferir ao usuário o controle sobre Mary" in context
    assert "peso emocional=10/10" in context
    assert "relevância relacional=10/10" in context


def test_baseline_memories_enter_first_finalized_turn() -> None:
    script = _script()
    state = PilotState(node_id=script.first_beat_id, facts={"user_name": "Janio"})

    turn = decide_editorial_progression_turn(script, state, "Oi, tudo bem?")

    active_ids = turn.state.facts["_active_memory_ids"].split(",")
    assert "marital_frustration" in active_ids
    assert "user_as_awakening_possibility" in active_ids
    assert "mary_tests_reciprocity_and_safety" in active_ids
    assert "EIXO RELACIONAL DE MARY" in turn.system_prompt
    assert "Mary percebe em Janio" in turn.system_prompt


def test_forgotten_and_superseded_memories_are_not_rendered() -> None:
    document = {
        "character": {"name": "Lia", "age": 30},
        "memories": {
            "active": {
                "summary": "Lia lembra do encontro.",
                "status": "active",
            },
            "old": {
                "summary": "Lia ainda usa um endereço antigo.",
                "status": "superseded",
            },
        },
    }

    context = build_narrative_context(document, ["active", "old"])

    assert "Lia lembra do encontro" in context
    assert "endereço antigo" not in context
