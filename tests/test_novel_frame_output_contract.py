from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services.novel_frame_output_contract import (
    FrameOutputContractError,
    enforce_frame_output_contract,
)


def _movement() -> SimpleNamespace:
    frame = {
        "frame_id": "encontro_020",
        "description": "Mary conclui o movimento.",
        "entries": [
            {"kind": "fala", "actor": "mary"},
            {"kind": "fala", "actor": "mary"},
            {"kind": "fala", "actor": "professor"},
            {"kind": "fala", "actor": "professor"},
        ],
    }
    return SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )


def test_removes_unexpected_thought_before_persistence() -> None:
    content = """[QUADRO encontro_020]
[DESCRIÇÃO]
Mary conclui o movimento.
[FALA mary|Mary]
Primeira fala.
[FALA mary|Mary]
Segunda fala.
[PENSAMENTO mary|Mary]
Pensamento indevido.
[FALA professor|Professor]
Terceira fala.
[FALA professor|Professor]
Quarta fala.
[/QUADRO]"""

    result = enforce_frame_output_contract(_movement(), content)

    assert "Pensamento indevido" not in result
    assert "[PENSAMENTO" not in result
    assert result.count("[FALA ") == 4


def test_rejects_missing_authored_entry() -> None:
    content = """[QUADRO encontro_020]
[DESCRIÇÃO]
Mary conclui o movimento.
[FALA mary|Mary]
Primeira fala.
[FALA professor|Professor]
Terceira fala.
[FALA professor|Professor]
Quarta fala.
[/QUADRO]"""

    with pytest.raises(FrameOutputContractError, match="ordem|omitiu"):
        enforce_frame_output_contract(_movement(), content)


def test_rejects_actor_change_that_could_mask_an_omission() -> None:
    content = """[QUADRO encontro_020]
[DESCRIÇÃO]
Mary conclui o movimento.
[FALA mary|Mary]
Primeira fala.
[FALA professor|Professor]
Fala no ator errado.
[FALA professor|Professor]
Terceira fala.
[FALA professor|Professor]
Quarta fala.
[/QUADRO]"""

    with pytest.raises(FrameOutputContractError, match="ordem|omitiu"):
        enforce_frame_output_contract(_movement(), content)


def test_restores_exact_authored_speech_changed_by_model() -> None:
    frame = {
        "frame_id": "encontro_001",
        "description": "Mary chega.",
        "entries": [
            {
                "kind": "fala",
                "actor": "mary",
                "instruction": "Oi, Janio... cheguei.",
                "delivery": "exata",
            }
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )
    content = """[QUADRO encontro_001]
[DESCRIÇÃO]
Mary chega.
[FALA mary|Mary]
Oi, Janio... finalmente cheguei.
[/QUADRO]"""

    result = enforce_frame_output_contract(movement, content)

    assert "Oi, Janio... cheguei." in result
    assert "finalmente" not in result


def test_accepts_literal_exact_authored_speech() -> None:
    frame = {
        "frame_id": "encontro_001",
        "description": "Mary chega.",
        "entries": [
            {
                "kind": "fala",
                "actor": "mary",
                "instruction": "Oi, Janio... cheguei.",
                "delivery": "exata",
            }
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )
    content = """[QUADRO encontro_001]
[DESCRIÇÃO]
Mary chega.
[FALA mary|Mary]
Oi, Janio... cheguei.
[/QUADRO]"""

    result = enforce_frame_output_contract(movement, content)

    assert "Oi, Janio... cheguei." in result
