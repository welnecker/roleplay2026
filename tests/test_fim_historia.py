from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services.editorial_content import _mark_explicit_story_end
from services.novel_v2_adapter import movement_from_script, next_movement_id


FRAME_PREFIX = "NOVEL_FRAME_V2\n"


def _document() -> dict[str, object]:
    return {
        "blocks": [
            {
                "beats": [
                    {
                        "beat_id": "quadro_001",
                        "required_movement": FRAME_PREFIX
                        + json.dumps(
                            {
                                "frame_id": "quadro_001",
                                "description": "Último quadro",
                                "entries": [
                                    {
                                        "kind": "fala",
                                        "actor": "mary",
                                        "instruction": "Fim.",
                                    }
                                ],
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        "next_beat_id": "quadro_999",
                        "allowed_transitions": {"engaged": "quadro_999"},
                    }
                ]
            }
        ]
    }


def test_fim_historia_marks_last_v2_frame_as_terminal() -> None:
    document = _document()
    rows = [
        {
            "line_id": "quadro_001_descricao",
            "order": 1,
            "instruction": "[DESCRIÇÃO] Último quadro",
            "status": "active",
        },
        {
            "line_id": "quadro_001_mary_fala_01",
            "order": 2,
            "instruction": "[FALA mary] Fim.",
            "status": "active",
        },
        {
            "line_id": "fim_001",
            "order": 3,
            "instruction": "[FIM_HISTORIA]",
            "status": "active",
        },
    ]

    marked = _mark_explicit_story_end(document, rows)
    beat = marked["blocks"][0]["beats"][0]
    payload = json.loads(beat["required_movement"][len(FRAME_PREFIX) :])

    assert payload["is_ending"] is True
    assert beat["next_beat_id"] == ""
    assert beat["allowed_transitions"] == {}


def test_fim_historia_must_be_last_active_line() -> None:
    document = _document()
    rows = [
        {
            "line_id": "fim_001",
            "order": 1,
            "instruction": "[FIM_HISTORIA]",
            "status": "active",
        },
        {
            "line_id": "depois",
            "order": 2,
            "instruction": "[FALA mary] Isto não pode vir depois.",
            "status": "active",
        },
    ]

    with pytest.raises(ValueError, match="última linha ativa"):
        _mark_explicit_story_end(document, rows)


def test_explicit_terminal_frame_propagates_to_runtime_movement() -> None:
    objective = FRAME_PREFIX + json.dumps(
        {"frame_id": "quadro_001", "is_ending": True},
        separators=(",", ":"),
    )
    script = SimpleNamespace(
        first_beat_id="quadro_001",
        endings={},
        beats={
            "quadro_001": {
                "objective": objective,
                "units": [],
                "on_user": {"engaged": "quadro_999"},
                "block_id": "novel_v2_frames",
            }
        },
    )

    movement = movement_from_script(script, "quadro_001")

    assert movement.is_ending is True
    assert next_movement_id(script, "quadro_001") == ""
