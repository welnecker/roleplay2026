from __future__ import annotations

import json

from services.editorial_episodic_memory import (
    advance_episode_turn,
    consolidate_bridge_episode,
    creativity_blocked,
    prepare_bridge_episode,
    recall_episode,
)


def _document():
    return {
        "runtime_policy": {
            "episodic_memory": {
                "history_turn_window": 3,
                "recall": [{"beat_prefixes": ["telefone_", "motel_"]}],
            }
        }
    }


def _bridge_facts() -> dict[str, str]:
    return {
        "_bridge_origin_objective": "Mary pergunta o nome do usuário.",
        "_bridge_origin_canonical": "Ainda nem sei seu nome.",
        "_bridge_target_objective": "Mary agradece a ajuda e segue para o carro.",
        "_bridge_target_canonical": "Obrigada pela ajuda. Vamos até o carro.",
    }


def _episode(facts):
    return json.loads(facts["_episodic_memory_json"])


def _turn(facts, amount=1):
    for _ in range(amount):
        advance_episode_turn(_document(), facts)


def test_routine_canonical_answer_does_not_claim_episode_slot() -> None:
    facts = _bridge_facts()
    _turn(facts)

    mode = prepare_bridge_episode(
        _document(),
        facts,
        "Meu nome é Janio.",
        source_beat_id="estacionamento_001",
    )

    assert mode == "ignored"
    assert "_episodic_memory_draft_json" not in facts
    assert "_episodic_memory_json" not in facts


def test_bridge_saves_user_and_mary_as_one_capsule() -> None:
    facts = _bridge_facts()
    _turn(facts)
    mode = prepare_bridge_episode(
        _document(),
        facts,
        "Eu pagaria pra ver a cor da sua calcinha.",
        source_beat_id="estacionamento_001",
    )
    assert mode == "new"

    consolidate_bridge_episode(
        facts,
        "Você é atrevido, mas agora fiquei curiosa para saber quanto pagaria.",
    )

    episode = _episode(facts)
    assert episode["episode_id"] == "creative_episode_001"
    assert "cor da sua calcinha" in episode["user_text"]
    assert "quanto pagaria" in episode["mary_text"]
    assert episode["status"] == "dormant"
    assert episode["eligible_after_turn"] == 5


def test_capsule_stays_dormant_until_exchange_leaves_recent_history() -> None:
    facts = _bridge_facts()
    _turn(facts)
    prepare_bridge_episode(
        _document(), facts, "Quero descobrir seu segredo.", source_beat_id="estacionamento_001"
    )
    consolidate_bridge_episode(facts, "Talvez um dia eu conte.")

    _turn(facts, 3)
    assert recall_episode(_document(), facts, beat_id="telefone_001") == ""

    _turn(facts)
    recalled = recall_episode(_document(), facts, beat_id="telefone_001")
    assert "Quero descobrir seu segredo" in recalled
    assert "Talvez um dia eu conte" in recalled
    assert _episode(facts)["status"] == "consumed"
    assert recall_episode(_document(), facts, beat_id="motel_001") == ""


def test_same_thread_updates_capsule_instead_of_creating_another() -> None:
    facts = _bridge_facts()
    _turn(facts)
    prepare_bridge_episode(
        _document(), facts, "Eu pagaria pra ver a cor da sua calcinha.", source_beat_id="estacionamento_001"
    )
    consolidate_bridge_episode(facts, "E quanto você pagaria?")

    _turn(facts)
    mode = prepare_bridge_episode(
        _document(), facts, "Pagaria bem pela cor da calcinha.", source_beat_id="estacionamento_002"
    )
    assert mode == "continue"
    consolidate_bridge_episode(facts, "Então continue curioso.")

    episode = _episode(facts)
    assert episode["episode_id"] == "creative_episode_001"
    assert episode["continuations"] == 1
    assert episode["latest_mary_text"] == "Então continue curioso."
    assert episode["eligible_after_turn"] == 6


def test_new_creativity_is_blocked_after_card_slot_was_used() -> None:
    facts = _bridge_facts()
    _turn(facts)
    prepare_bridge_episode(
        _document(), facts, "Quero descobrir seu segredo.", source_beat_id="estacionamento_001"
    )
    consolidate_bridge_episode(facts, "Talvez eu conte depois.")

    _turn(facts)
    mode = prepare_bridge_episode(
        _document(), facts, "Vamos viajar juntos amanhã.", source_beat_id="estacionamento_002"
    )

    assert mode == "blocked"
    assert creativity_blocked(facts)
    assert _episode(facts)["user_text"] == "Quero descobrir seu segredo."
    assert "_episodic_memory_draft_json" not in facts


def test_terms_are_not_predeclared_or_topic_specific() -> None:
    facts = _bridge_facts()
    _turn(facts)
    mode = prepare_bridge_episode(
        _document(),
        facts,
        "Quero plantar uma jabuticabeira na lua com você.",
        source_beat_id="estacionamento_001",
    )
    assert mode == "new"
    consolidate_bridge_episode(facts, "Essa foi a proposta mais improvável que ouvi hoje.")

    episode = _episode(facts)
    assert "jabuticabeira" in episode["anchors"]
    assert "lua" not in episode["anchors"]
    assert "jabuticabeira na lua" in episode["user_text"]
