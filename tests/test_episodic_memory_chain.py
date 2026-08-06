from __future__ import annotations

import json

from services.editorial_episodic_memory import capture_episode, recall_episode


def _document():
    return {
        "runtime_policy": {
            "episodic_memory": {
                "max_memories": 12,
                "recall": [
                    {
                        "beat_prefixes": ["mensagens_iniciais_", "video_"],
                        "tags": ["action", "initiative", "desire", "marriage"],
                    },
                    {
                        "beat_prefixes": ["motel_"],
                        "tags": ["lingerie", "desire", "phone", "action"],
                    },
                ],
            }
        }
    }


def _memories(facts):
    return json.loads(facts["_episodic_memory_json"])


def test_pending_memory_is_recalled_once_and_then_resolved() -> None:
    facts: dict[str, str] = {}
    capture_episode(
        _document(),
        facts,
        "Você quer ação, ou não?",
        source_beat_id="porta_malas_conversa_001",
    )

    recalled = recall_episode(_document(), facts, beat_id="mensagens_iniciais_003")
    assert "ação" in recalled
    assert _memories(facts)[0]["status"] == "recalled"

    capture_episode(
        _document(),
        facts,
        "Quis dizer que gosto de mulher com iniciativa.",
        source_beat_id="mensagens_iniciais_003",
    )
    assert _memories(facts)[0]["status"] == "resolved"
    assert recall_episode(_document(), facts, beat_id="video_003") == ""


def test_newer_lingerie_memory_can_replace_resolved_action_thread() -> None:
    facts: dict[str, str] = {}
    capture_episode(
        _document(), facts, "Você quer ação, ou não?", source_beat_id="estacionamento_001"
    )
    recall_episode(_document(), facts, beat_id="mensagens_iniciais_002")
    capture_episode(
        _document(),
        facts,
        "Quis dizer que gosto de iniciativa e queria te ver só de calcinha.",
        source_beat_id="mensagens_iniciais_002",
    )

    recalled = recall_episode(_document(), facts, beat_id="motel_001")
    assert "calcinha" in recalled
    assert "quer ação" not in recalled


def test_only_one_relevant_memory_is_returned() -> None:
    facts: dict[str, str] = {}
    capture_episode(_document(), facts, "Você é feliz casada?", source_beat_id="mercado_001")
    capture_episode(
        _document(), facts, "Eu queria te ver de lingerie.", source_beat_id="video_001"
    )

    recalled = recall_episode(_document(), facts, beat_id="motel_002")
    assert recalled.count("O usuário disse:") == 1
    assert "lingerie" in recalled
