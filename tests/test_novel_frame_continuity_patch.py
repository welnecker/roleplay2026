from __future__ import annotations

import json
from types import SimpleNamespace

from services import novel_frame_continuity_patch as continuity
from services import novel_frame_patch


def test_frame_payload_carries_generic_canonical_continuity(monkeypatch) -> None:
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
        "character_core": {"summary": "Personagem casada com o protagonista."},
        "runtime_rules": [
            "O professor é um terceiro personagem e não possui nome canônico.",
            "Nunca inventar um nome para o professor.",
        ],
    }

    result = continuity._compile_with_continuity(
        base_document,
        [],
        script_version="200",
    )
    movement = result["blocks"][0]["beats"][0]["required_movement"]
    payload = json.loads(movement[len(novel_frame_patch._FRAME_PREFIX) :])

    assert payload["continuity_contract"]["character_summary"] == (
        "Personagem casada com o protagonista."
    )
    assert payload["continuity_contract"]["runtime_rules"] == [
        "O professor é um terceiro personagem e não possui nome canônico.",
        "Nunca inventar um nome para o professor.",
    ]


def test_frame_prompt_rejects_stale_names_from_history(monkeypatch) -> None:
    frame = {
        "frame_id": "cena_002",
        "description": "",
        "entries": [],
        "continuity_contract": {
            "runtime_rules": [
                "O professor é um terceiro personagem e não possui nome canônico."
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
        character_name="Mary",
        user_name="Janio",
        movement=movement,
    )

    assert "PREVALECE SOBRE O HISTÓRICO" in prompt
    assert "Nomes próprios presentes apenas no histórico" in prompt
    assert "nunca pode renomear personagens" in prompt
    assert "não possui nome canônico" in prompt
