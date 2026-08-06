from __future__ import annotations

import json

from services.editorial_content import load_source_document
from services.editorial_memory_lifecycle import (
    eligible_memory_ids,
    render_memory_lifecycle_guidance,
    update_memory_lifecycle,
)
from services.editorial_runtime_impl import PilotState


def _document() -> dict:
    return {
        "memory_lifecycle": {
            "initial_strength": 4,
            "write_boost": 3,
            "recall_boost": 2,
            "decay_per_unobserved_turn": 1,
            "dormant_at": 2,
            "archive_at": 1,
            "archive_after_dormant_turns": 2,
            "protected_categories": ["relationship_origin"],
        },
        "memories": {
            "origin": {
                "category": "relationship_origin",
                "importance": 10,
                "summary": "Origem da relação.",
            },
            "event": {
                "category": "event",
                "importance": 5,
                "summary": "Um acontecimento passageiro.",
            },
        },
    }


def _lifecycle(state: PilotState) -> dict:
    return json.loads(state.facts["_memory_lifecycle_json"])


def test_card_declara_ciclo_de_vida_e_memorias_centrais_protegidas() -> None:
    document = load_source_document()
    policy = document["memory_lifecycle"]

    assert policy["dormant_at"] == 3
    assert policy["archive_after_dormant_turns"] == 4
    assert set(policy["protected_memory_ids"]) == {
        "marital_frustration",
        "user_as_awakening_possibility",
        "mary_tests_reciprocity_and_safety",
    }


def test_memoria_nao_observada_enfraquece_adormece_e_depois_e_arquivada() -> None:
    document = _document()
    state = PilotState()

    for turn in range(1, 6):
        state, _ = update_memory_lifecycle(
            document,
            state,
            ["event"],
            fingerprint=f"turn-{turn}",
        )

    assert _lifecycle(state)["event"]["status"] == "archived"
    assert eligible_memory_ids(document, ["event"], state.facts) == []


def test_memoria_protegida_nao_adormece_nem_e_arquivada() -> None:
    document = _document()
    state = PilotState()

    for turn in range(1, 10):
        state, _ = update_memory_lifecycle(
            document,
            state,
            ["origin"],
            fingerprint=f"turn-{turn}",
        )

    lifecycle = _lifecycle(state)["origin"]
    assert lifecycle["protected"] is True
    assert lifecycle["status"] == "active"
    assert eligible_memory_ids(document, ["origin"], state.facts) == ["origin"]


def test_nova_escrita_reativa_memoria_arquivada() -> None:
    document = _document()
    state = PilotState()

    for turn in range(1, 6):
        state, _ = update_memory_lifecycle(
            document,
            state,
            ["event"],
            fingerprint=f"turn-{turn}",
        )
    assert _lifecycle(state)["event"]["status"] == "archived"

    state, states = update_memory_lifecycle(
        document,
        state,
        ["event"],
        written_ids=["event"],
        fingerprint="reactivation",
    )

    assert states[0].status == "active"
    assert states[0].write_count == 1
    assert eligible_memory_ids(document, ["event"], state.facts) == ["event"]


def test_recall_reforca_memoria_sem_duplicar_o_mesmo_turno() -> None:
    document = _document()
    state = PilotState()

    state, first = update_memory_lifecycle(
        document,
        state,
        ["event"],
        recalled_ids=["event"],
        fingerprint="same-turn",
    )
    state, second = update_memory_lifecycle(
        document,
        state,
        ["event"],
        recalled_ids=["event"],
        fingerprint="same-turn",
    )

    assert first[0].recall_count == 1
    assert second[0].recall_count == 1
    assert first[0].strength == second[0].strength


def test_prompt_nao_expoe_ids_forca_idade_ou_contagens() -> None:
    document = _document()
    state = PilotState()
    state, states = update_memory_lifecycle(
        document,
        state,
        ["event"],
        recalled_ids=["event"],
        fingerprint="render",
    )

    prompt = render_memory_lifecycle_guidance(states)

    assert "CICLO DE VIDA DAS MEMÓRIAS" in prompt
    assert "event" not in prompt
    assert "strength" not in prompt
    assert "recall_count" not in prompt
