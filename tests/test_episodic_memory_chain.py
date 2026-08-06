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
from services.editorial_turn_finalization import _current_user_text


def _document():
    return {
        "runtime_policy": {
            "episodic_memory": {
                "recall": [{"beat_ids": ["estacionamento_conversa_001"], "beat_prefixes": ["motel_"]}]
            }
        }
    }


def test_unmarked_interaction_never_creates_memory() -> None:
    facts: dict[str, str] = {}
    advance_episode_turn(_document(), facts)
    assert prepare_selected_memory(
        _document(), facts, "Você é muito atenciosa.",
        source_beat_id="encontro_acidental_002", runtime_phase="bridge"
    ) == "ignored"
    consolidate_selected_memory(facts, "Obrigada por dizer isso.")
    assert continuity_memories(facts) == []
    assert relationship_recollections(facts) == []


def test_marked_bridge_creates_consumable_thread() -> None:
    facts: dict[str, str] = {}
    mark_memory_requested(facts, True)
    advance_episode_turn(_document(), facts)
    assert prepare_selected_memory(
        _document(), facts,
        "Eu queria te perguntar uma coisa, mas aqui parece perigoso.",
        source_beat_id="reencontro_fila_006", runtime_phase="bridge"
    ) == "continuity"
    consolidate_selected_memory(facts, "No estacionamento você me conta.")
    assert continuity_memories(facts)[0]["status"] == "available"

    assert recall_episode(_document(), facts, beat_id="reencontro_fila_007") == ""
    for _ in range(10):
        advance_episode_turn(_document(), facts)
    recalled = recall_episode(_document(), facts, beat_id="estacionamento_conversa_001")
    assert "queria te perguntar" in recalled
    assert continuity_memories(facts)[0]["status"] == "consumed"
    assert recall_episode(_document(), facts, beat_id="motel_001") == ""


def test_marked_canonical_beat_creates_persistent_recollection() -> None:
    facts: dict[str, str] = {}
    mark_memory_requested(facts, True)
    advance_episode_turn(_document(), facts)
    assert prepare_selected_memory(
        _document(), facts, "Moro no bloco B do Plaza.",
        source_beat_id="encontro_acidental_004", runtime_phase="canonical"
    ) == "recollection"
    consolidate_selected_memory(facts, "Então somos vizinhos, eu também moro no Plaza.")
    recollection = relationship_recollections(facts)[0]
    assert recollection["status"] == "active"
    rendered = render_relationship_recollections(facts)
    assert "bloco B" in rendered
    assert "somos vizinhos" in rendered
    assert render_relationship_recollections(facts) == rendered


def test_type_is_derived_only_from_runtime_phase() -> None:
    bridge: dict[str, str] = {}
    canonical: dict[str, str] = {}
    mark_memory_requested(bridge, True)
    mark_memory_requested(canonical, True)
    advance_episode_turn(_document(), bridge)
    advance_episode_turn(_document(), canonical)
    assert prepare_selected_memory(
        _document(), bridge, "A mesma fala.", source_beat_id="beat_001", runtime_phase="bridge"
    ) == "continuity"
    assert prepare_selected_memory(
        _document(), canonical, "A mesma fala.", source_beat_id="beat_001", runtime_phase="canonical"
    ) == "recollection"


def test_bridge_multiline_user_text_keeps_user_authored_uppercase_label() -> None:
    prompt = (
        "FASE ESTRUTURAL: PONTE NARRATIVA.\n"
        "FALA ATUAL DO USUÁRIO: Primeiro parágrafo.\n\n"
        "OBSERVAÇÃO: isto ainda pertence à mensagem do usuário.\n\n"
        "Terceiro parágrafo.\n"
        "BEAT DE ORIGEM: reencontro_fila_006\n"
        "MOVIMENTO DE ORIGEM JÁ CONCLUÍDO — PROIBIDO REPETIR: teste"
    )
    extracted = _current_user_text(prompt)
    assert "Primeiro parágrafo" in extracted
    assert "OBSERVAÇÃO:" in extracted
    assert "Terceiro parágrafo" in extracted
    assert "BEAT DE ORIGEM" not in extracted


def test_canonical_multiline_user_text_keeps_user_authored_uppercase_label() -> None:
    prompt = (
        "REGRAS ABSOLUTAS:\n- teste\n"
        "RESPOSTA DO USUÁRIO: Primeiro parágrafo.\n\n"
        "OBSERVAÇÃO: isto ainda pertence à mensagem do usuário.\n\n"
        "Terceiro parágrafo.\n"
        "UNIDADES DO MOVIMENTO:\n- dialogue: teste"
    )
    extracted = _current_user_text(prompt)
    assert "Primeiro parágrafo" in extracted
    assert "OBSERVAÇÃO:" in extracted
    assert "Terceiro parágrafo" in extracted
    assert "UNIDADES DO MOVIMENTO" not in extracted
