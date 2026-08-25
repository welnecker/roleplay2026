from __future__ import annotations

import json
from types import SimpleNamespace

from services import novel_frame_continuity_patch as continuity
from services import novel_frame_patch


def test_frame_payload_carries_authoritative_core_rules(monkeypatch) -> None:
    frame = {"frame_id": "cena_001", "description": "", "entries": []}
    compiled = {
        "blocks": [
            {
                "beats": [
                    {
                        "required_movement": novel_frame_patch._FRAME_PREFIX
                        + json.dumps(frame, ensure_ascii=False)
                    }
                ]
            }
        ]
    }

    monkeypatch.setattr(
        continuity,
        "_original_compile_novel_frame_story",
        lambda *_args, **_kwargs: compiled,
    )
    base_document = {
        "character_core": {
            "summary": "Personagem casada com o protagonista.",
            "dominant_drive": [
                "Um terceiro personagem permanece distinto do protagonista.",
                "Um personagem sem nome canônico não recebe nome inventado.",
            ],
            "thought_rules": [
                "Não inventar passado nem características ausentes de terceiros."
            ],
            "response_rules": [
                "Preservar os papéis declarados pelo roteiro."
            ],
        }
    }

    result = continuity._compile_with_continuity(
        base_document,
        [],
        script_version="200",
    )
    movement = result["blocks"][0]["beats"][0]["required_movement"]
    payload = json.loads(movement[len(novel_frame_patch._FRAME_PREFIX) :])
    contract = payload["continuity_contract"]

    assert contract["character_summary"] == "Personagem casada com o protagonista."
    assert contract["identity_rules"] == [
        "Um terceiro personagem permanece distinto do protagonista.",
        "Um personagem sem nome canônico não recebe nome inventado.",
    ]
    assert contract["thought_rules"] == [
        "Não inventar passado nem características ausentes de terceiros."
    ]
    assert contract["response_rules"] == [
        "Preservar os papéis declarados pelo roteiro."
    ]


def test_frame_prompt_rejects_noncanonical_history_facts(monkeypatch) -> None:
    frame = {
        "frame_id": "cena_002",
        "description": "",
        "entries": [],
        "continuity_contract": {
            "identity_rules": [
                "Um personagem sem nome canônico não recebe nome inventado."
            ]
        },
    }
    movement = SimpleNamespace(
        instruction=novel_frame_patch._FRAME_PREFIX
        + json.dumps(frame, ensure_ascii=False)
    )
    monkeypatch.setattr(
        continuity,
        "_original_build_frame_prompt",
        lambda **_kwargs: "PROMPT BASE",
    )

    prompt = continuity._build_frame_prompt_with_continuity(
        character_name="Personagem",
        user_name="Usuario",
        movement=movement,
    )

    assert "PREVALECE SOBRE O HISTÓRICO" in prompt
    assert "fatos biográficos presentes apenas no histórico" in prompt
    assert "nunca pode renomear personagens" in prompt
    assert "sem nome canônico" in prompt
