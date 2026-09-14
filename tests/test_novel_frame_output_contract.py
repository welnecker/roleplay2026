from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from services.novel_frame_output_contract import (
    FrameOutputContractError,
    authored_frame_content,
    enforce_frame_output_contract,
    frame_requires_generation,
    interpreted_lines_prompt,
    merge_interpreted_lines,
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


def test_reinsere_smack_autoral_antes_da_fala_sem_depender_do_modelo() -> None:
    frame = {
        "frame_id": "mascara_001",
        "description": "O professor beija o ombro de Mary.",
        "entries": [
            {
                "kind": "fala",
                "actor": "mary",
                "instruction": "Ai!!! Que susto, prof... rsrs",
                "effects_before": [
                    {
                        "kind": "smack",
                        "text": "SMACK!",
                        "x": 69,
                        "y": 48,
                        "delay": 350,
                        "duration": 1200,
                        "dx": 32,
                        "dy": -10,
                    }
                ],
            }
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )
    content = """[QUADRO mascara_001]
[DESCRIÇÃO]
O professor beija o ombro de Mary.
[FALA mary|Mary]
Ai!!! Que susto, prof... rsrs
[/QUADRO]"""

    result = enforce_frame_output_contract(movement, content)

    assert "[ONOMATOPEIA smack x=69 y=48 delay=350 duracao=1200 dx=32 dy=-10]" in result
    assert result.index("[ONOMATOPEIA") < result.index("[FALA mary|Mary]")



def test_authored_frame_does_not_require_generation_and_preserves_text() -> None:
    frame = {
        "frame_id": "degustacao_001",
        "description": "Camilly encontra {{nome}} e sorri com malícia.",
        "entries": [
            {
                "kind": "fala",
                "actor": "camilly",
                "instruction": "Oi, {{nome}}... finalmente você chegou.",
                "delivery": "adaptavel",
            },
            {
                "kind": "pensamento",
                "actor": "camilly",
                "instruction": "Quero descobrir até onde ele pretende ir...",
            },
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )

    assert frame_requires_generation(movement) is False
    result = authored_frame_content(
        movement,
        character_name="Camilly",
        user_name="Janio",
    )

    assert "[QUADRO degustacao_001]" in result
    assert "Camilly encontra Janio e sorri com malícia." in result
    assert "Oi, Janio... finalmente você chegou." in result
    assert "[PENSAMENTO camilly|Camilly]" in result


def test_only_interpreted_speech_requires_generation() -> None:
    frame = {
        "frame_id": "degustacao_002",
        "description": "Camilly sustenta o olhar.",
        "entries": [
            {
                "kind": "fala",
                "actor": "camilly",
                "instruction": "Provoque {{nome}} com malícia.",
                "delivery": "interpretada",
            }
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )

    assert frame_requires_generation(movement) is True
    with pytest.raises(FrameOutputContractError, match="exige geração"):
        authored_frame_content(
            movement,
            character_name="Camilly",
            user_name="Janio",
        )



def test_mixed_frame_generates_only_interpreted_lines() -> None:
    frame = {
        "frame_id": "degustacao_003",
        "description": "Camilly se aproxima de {{nome}}.",
        "entries": [
            {
                "kind": "fala",
                "actor": "camilly",
                "line_id": "fala_fixa",
                "instruction": "Você demorou...",
                "delivery": "exata",
            },
            {
                "kind": "fala",
                "actor": "camilly",
                "line_id": "fala_ia",
                "instruction": "Provoque {{nome}} sobre o atraso.",
                "delivery": "interpretada",
            },
            {
                "kind": "pensamento",
                "actor": "camilly",
                "line_id": "pensamento_fixo",
                "instruction": "Quero entender suas intenções.",
            },
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )

    prompt = interpreted_lines_prompt(
        movement,
        character_name="Camilly",
        user_name="Janio",
    )
    assert "fala_ia" in prompt
    assert "Provoque Janio" in prompt

    result = merge_interpreted_lines(
        movement,
        """[FALA_INTERPRETADA fala_ia]
Demorou de propósito só para me deixar curiosa?
[/FALA_INTERPRETADA]""",
        character_name="Camilly",
        user_name="Janio",
    )

    assert "Camilly se aproxima de Janio." in result
    assert "Você demorou..." in result
    assert "Demorou de propósito só para me deixar curiosa?" in result
    assert "Quero entender suas intenções." in result
    assert "Provoque Janio" not in result


def test_mixed_frame_rejects_missing_interpreted_line() -> None:
    frame = {
        "frame_id": "degustacao_004",
        "description": "Camilly observa.",
        "entries": [
            {
                "kind": "fala",
                "actor": "camilly",
                "line_id": "fala_ia_1",
                "instruction": "Primeira provocação.",
                "delivery": "interpretada",
            },
            {
                "kind": "fala",
                "actor": "camilly",
                "line_id": "fala_ia_2",
                "instruction": "Segunda provocação.",
                "delivery": "interpretada",
            },
        ],
    }
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n" + json.dumps(frame, ensure_ascii=False)
    )

    with pytest.raises(FrameOutputContractError, match="exatamente"):
        merge_interpreted_lines(
            movement,
            """[FALA_INTERPRETADA fala_ia_1]
Uma fala apenas.
[/FALA_INTERPRETADA]""",
            character_name="Camilly",
            user_name="Janio",
        )
