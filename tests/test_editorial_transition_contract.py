from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_runtime_impl import PilotScript, PilotState, decide_turn


def _document() -> dict:
    return {
        "introduction": "Teste de transição",
        "engagement_policy": {"categories": {"engaged": {}}},
        "blocks": [
            {
                "block_id": "bloco",
                "order": 1,
                "entry_beat_id": "beat_001",
                "beats": [
                    {
                        "beat_id": "beat_001",
                        "order": 1,
                        "type": "dialogue",
                        "canonical_line": "Primeira fala",
                        "required_movement": "Abrir a conversa.",
                        "dramatic_direction": "",
                        "next_beat_id": "beat_002",
                        "allowed_transitions": {"engaged": "beat_002"},
                    },
                    {
                        "beat_id": "beat_002",
                        "order": 2,
                        "type": "dialogue",
                        "canonical_line": "Segunda fala",
                        "required_movement": "Continuar a conversa.",
                        "dramatic_direction": "",
                        "next_beat_id": "end_ok",
                        "allowed_transitions": {"engaged": "end_ok"},
                    },
                    {
                        "beat_id": "end_ok",
                        "order": 3,
                        "type": "ending",
                        "canonical_line": "Fim",
                        "ending": {"run_status": "completed", "ending_code": "ok"},
                    },
                ],
            }
        ],
    }


def test_proximo_beat_nao_e_compilado_como_encerramento_terminal() -> None:
    compiled = compile_editorial_document(_document())
    script = PilotScript(compiled)

    assert script.beats["beat_001"]["on_user"]["engaged"] == "beat_002"
    assert script.beats["beat_001"]["terminal_transition"] == ""

    turn = decide_turn(script, PilotState(node_id="beat_001"), "Tudo bem")

    assert turn.target_id == "beat_002"
    assert turn.finished is False
    assert turn.state.node_id == "beat_002"
