from __future__ import annotations

import json
from types import SimpleNamespace

from services.novel_frame_output_contract import frame_generation_instruction
from services.novel_frame_runtime_support import build_runtime_prompt


def test_flet_usa_prompt_multipersonagem_para_quadro_v2() -> None:
    movement = SimpleNamespace(
        instruction="NOVEL_FRAME_V2\n"
        + json.dumps(
            {
                "frame_id": "encontro_001",
                "description": "Mary entra na casa.",
                "entries": [
                    {
                        "kind": "pensamento",
                        "actor": "mary",
                        "instruction": "Coragem, Mary...",
                    },
                    {
                        "kind": "pensamento",
                        "actor": "mary",
                        "instruction": "Que bela casa...",
                    },
                ],
            },
            ensure_ascii=False,
        )
    )

    prompt = build_runtime_prompt(
        character_name="Mary",
        user_name="Janio",
        movement=movement,
    )

    assert "QUADRO MULTIPERSONAGEM" in prompt
    assert "CADA entry do roteiro, na MESMA ORDEM" in prompt
    assert "Se o roteiro possui quatro entries, devolva exatamente quatro blocos" in prompt
    assert "Entregue somente a fala de Mary" not in prompt
    assert '"kind": "pensamento"' in prompt
    assert '"visible_name": "Mary"' in prompt


def test_retry_exige_mesma_estrutura_sem_tornar_fala_interpretada_literal() -> None:
    instruction = frame_generation_instruction(1)

    assert "correspondência estrutural 1:1" in instruction
    assert "mesmo tipo e actor" in instruction
    assert "Respeite a modalidade delivery" in instruction
    assert "Emita exatamente as entries autorais" not in instruction
