from __future__ import annotations

from services.editorial_episodic_memory import (
    advance_episode_turn,
    consolidate_selected_memory,
    continuity_memories,
    mark_memory_requested,
    prepare_selected_memory,
    recall_episode,
    relationship_recollections,
    render_relationship_recollections,
)


def _document():
    return {
        "runtime_policy": {
            "episodic_memory": {
                "recall": [
                    {
                        "beat_ids": ["estacionamento_conversa_001"],
                        "beat_prefixes": ["motel_"],
                    }
                ]
            }
        }
    }


def test_unmarked_interaction_never_creates_memory() -> None:
    facts: dict[str, str] = {}
    advance_episode_turn(_document(), facts)
    mode = prepare_selected_memory(
        _document(),
        facts,
        "Você é muito atenciosa.",
        source_beat_id="encontro_acidental_002",
        runtime_phase="bridge",
    )
    consolidate_selected_memory(facts, "Obrigada por dizer isso.")
    assert mode == "ignored"
    assert continuity_memories(facts) == []
    assert relationship_recollections(facts) == []


def test_marked_bridge_creates_consumable_continuity_thread() -> None:
    facts: dict[str, str] = {}
    mark_memory_requested(facts, True)
    advance_episode_turn(_document(), facts)
    mode = prepare_selected_memory(
        _document(),
        facts,
        "Eu queria te perguntar uma coisa, mas aqui parece perigoso.",
        source_beat_id="reencontro_fila_006",
        runtime_phase="bridge",
    )
    assert mode == "continuity"

    consolidate_selected_memory(
        facts,
        "Aqui não. Quando chegarmos ao estacionamento, você me conta.",
    )

    threads = continuity_memories(facts)
    assert len(threads) == 1
    assert threads[0]["status"] == "available"
    assert "queria te perguntar" in threads[0]["user_text"]
    assert "estacionamento" in threads[0]["mary_text"]


def test_script_can_recall_thread_immediately_or_n_turns_later() -> None:
    facts: dict[str, str] = {}
    mark_memory_requested(facts, True)
    advance_episode_turn(_document(), facts)
    prepare_selected_memory(
        _document(),
        facts,
        "Depois eu quero te contar um segredo.",
        source_beat_id="reencontro_fila_006",
        runtime_phase="bridge",
    )
    consolidate_selected_memory(facts, "Tudo bem, me conta quando se sentir à vontade.")

    # Beat não habilitado: a memória permanece disponível.
    assert recall_episode(_document(), facts, beat_id="reencontro_fila_007") == ""
    assert continuity_memories(facts)[0]["status"] == "available"

    # Pode passar qualquer quantidade de turnos sem perda.
    for _ in range(12):
        advance_episode_turn(_document(), facts)

    recalled = recall_episode(
        _document(), facts, beat_id="estacionamento_conversa_001"
    )
    assert "contar um segredo" in recalled
    assert continuity_memories(facts)[0]["status"] == "consumed"
    assert recall_episode(_document(), facts, beat_id="motel_001") == ""


def test_marked_canonical_beat_creates_persistent_recollection() -> None:
    facts: dict[str, str] = {}
    mark_memory_requested(facts, True)
    advance_episode_turn(_document(), facts)
    mode = prepare_selected_memory(
        _document(),
        facts,
        "Moro no bloco B do Plaza.",
        source_beat_id="encontro_acidental_004",
        runtime_phase="canonical",
    )
    assert mode == "recollection"

    consolidate_selected_memory(facts, "Então somos vizinhos, eu também moro no Plaza.")

    recollections = relationship_recollections(facts)
    assert len(recollections) == 1
    assert recollections[0]["status"] == "active"
    rendered = render_relationship_recollections(facts)
    assert "Moro no bloco B do Plaza" in rendered
    assert "somos vizinhos" in rendered

    # Lembranças cotidianas não são consumidas pelo uso no prompt.
    assert render_relationship_recollections(facts) == rendered
    assert relationship_recollections(facts)[0]["status"] == "active"


def test_same_turn_type_is_derived_only_from_runtime_phase() -> None:
    bridge_facts: dict[str, str] = {}
    canonical_facts: dict[str, str] = {}

    mark_memory_requested(bridge_facts, True)
    mark_memory_requested(canonical_facts, True)
    advance_episode_turn(_document(), bridge_facts)
    advance_episode_turn(_document(), canonical_facts)

    assert prepare_selected_memory(
        _document(),
        bridge_facts,
        "A mesma fala pode ter funções diferentes.",
        source_beat_id="beat_001",
        runtime_phase="bridge",
    ) == "continuity"
    assert prepare_selected_memory(
        _document(),
        canonical_facts,
        "A mesma fala pode ter funções diferentes.",
        source_beat_id="beat_001",
        runtime_phase="canonical",
    ) == "recollection"
