from __future__ import annotations

import pytest

from services.editorial_compiler import compile_editorial_document
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _document() -> dict[str, object]:
    return {
        "format_version": 1,
        "package_id": "test.structural_yard",
        "introduction": "Card mínimo para provar invariantes do runtime.",
        "character": {"name": "Lia", "age": 30},
        "blocks": [
            {
                "block_id": "main",
                "order": 1,
                "entry_beat_id": "main_001",
                "beats": [
                    {
                        "beat_id": "main_001",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Oferecer continuidade.",
                        "canonical_line": "Podemos continuar.",
                        "allowed_transitions": {
                            "engaged": "yard_exit_001",
                            "minimal": "yard_exit_001",
                            "dismissive": "yard_exit_001",
                            "nonsense": "yard_exit_001",
                        },
                    }
                ],
            },
            {
                "block_id": "yard_exit",
                "block_type": "terminal_yard",
                "order": 2,
                "entry_beat_id": "yard_exit_001",
                "min_user_turns": 2,
                "max_user_turns": 2,
                "rules": ["Não retornar ao bloco principal."],
                "beats": [
                    {
                        "beat_id": "yard_exit_001",
                        "order": 1,
                        "type": "dialogue",
                        "required_movement": "Iniciar despedida.",
                        "canonical_line": "Tudo bem, vamos encerrar com calma.",
                        "allowed_transitions": {
                            "engaged": "yard_exit_002",
                            "minimal": "yard_exit_002",
                            "dismissive": "yard_exit_002",
                            "nonsense": "yard_exit_002",
                        },
                    },
                    {
                        "beat_id": "yard_exit_002",
                        "order": 2,
                        "type": "dialogue",
                        "required_movement": "Concluir despedida.",
                        "canonical_line": "Foi bom conversar com você.",
                        "allowed_transitions": {
                            "engaged": "end_exit",
                            "minimal": "end_exit",
                            "dismissive": "end_exit",
                            "nonsense": "end_exit",
                        },
                    },
                ],
            },
            {
                "block_id": "endings",
                "order": 3,
                "entry_beat_id": "end_exit",
                "beats": [
                    {
                        "beat_id": "end_exit",
                        "order": 1,
                        "type": "ending",
                        "canonical_line": "Até outra hora.",
                        "ending": {
                            "run_status": "completed",
                            "ending_code": "test_exit",
                        },
                    }
                ],
            },
        ],
    }


def _script() -> PilotScript:
    return prepare_editorial_script(PilotScript(compile_editorial_document(_document())))


def test_compilador_preserva_catalogo_e_metadados_do_patio() -> None:
    script = _script()

    yard = script.scene["terminal_yards"]["yard_exit"]
    assert yard["entry_beat_id"] == "yard_exit_001"
    assert yard["beat_ids"] == ["yard_exit_001", "yard_exit_002"]
    assert yard["min_user_turns"] == 2
    assert yard["max_user_turns"] == 2
    assert yard["ending_ids"] == ["end_exit"]

    first = script.beats["yard_exit_001"]
    assert first["block_type"] == "terminal_yard"
    assert first["terminal_yard_id"] == "yard_exit"
    assert first["position_in_block"] == 1
    assert first["block_size"] == 2


def test_entrada_ativa_fase_terminal_e_percorre_ate_ending() -> None:
    script = _script()
    state = PilotState(node_id="main_001")

    entered = decide_editorial_progression_turn(script, state, "Prefiro encerrar.")
    assert entered.target_id == "yard_exit_001"
    assert entered.finished is False
    assert entered.state.facts["_runtime_phase"] == "terminal_yard"
    assert entered.state.facts["_active_yard_id"] == "yard_exit"
    assert entered.state.facts["_yard_user_turn_count"] == "0"

    second = decide_editorial_progression_turn(
        script,
        entered.state,
        "Antes, posso fazer uma pergunta pessoal?",
    )
    assert second.target_id == "yard_exit_002"
    assert second.state.facts["_runtime_phase"] == "terminal_yard"
    assert second.state.facts["_yard_user_turn_count"] == "1"

    ended = decide_editorial_progression_turn(
        script,
        second.state,
        "Pensando melhor, quero voltar e continuar.",
    )
    assert ended.target_id == "end_exit"
    assert ended.finished is True
    assert ended.state.finished is True
    assert ended.state.ending_code == "test_exit"
    assert ended.state.facts["_runtime_phase"] == "finished"
    assert "_active_yard_id" not in ended.state.facts


def test_estado_de_patio_inconsistente_falha_em_vez_de_escapar() -> None:
    script = _script()
    state = PilotState(
        node_id="main_001",
        facts={
            "_runtime_phase": "terminal_yard",
            "_active_yard_id": "yard_exit",
            "_yard_user_turn_count": "0",
        },
    )

    with pytest.raises(RuntimeError, match="node_id está fora"):
        decide_editorial_progression_turn(script, state, "Quero continuar.")
