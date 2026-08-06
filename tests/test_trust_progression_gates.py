from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_progression_gates import (
    evaluate_progression_gate,
    projected_dimension_value,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_card_declara_confianca_como_condicao_real() -> None:
    document = load_source_document()
    beats = {
        beat["beat_id"]: beat
        for block in document["blocks"]
        for beat in block.get("beats", [])
    }

    confession = beats["mensagens_iniciais_009"]["progression_gate"]
    video = beats["video_002"]["progression_gate"]
    assert confession == {
        "dimension": "trust",
        "min": 5,
        "fallback_target": "mensagens_iniciais_008",
        "blocked_instruction": confession["blocked_instruction"],
    }
    assert video["min"] == 7
    assert video["fallback_target"] == "video_001"


def test_interacao_atual_pode_liberar_o_destino() -> None:
    document = load_source_document()
    state = PilotState(trust=4)
    target = {"progression_gate": {"dimension": "trust", "min": 5}}

    assert projected_dimension_value(document, state, "engaged", "trust") == 5
    assert evaluate_progression_gate(document, state, target, "engaged").allowed is True


def test_confianca_baixa_redireciona_para_contencao_natural() -> None:
    script = _script()
    state = PilotState(node_id="mensagens_iniciais_008", trust=2)

    turn = decide_editorial_progression_turn(script, state, "Pode continuar, Mary.")

    assert turn.target_id == "mensagens_iniciais_008"
    assert turn.state.facts["_progression_gate_blocked_target"] == "mensagens_iniciais_009"
    assert turn.state.facts["_progression_gate_dimension"] == "trust"
    assert "CONFIANÇA AINDA INSUFICIENTE" in turn.system_prompt
    assert "limiares" in turn.system_prompt


def test_confianca_suficiente_libera_confissao() -> None:
    script = _script()
    state = PilotState(node_id="mensagens_iniciais_008", trust=4)

    turn = decide_editorial_progression_turn(script, state, "Pode continuar, Mary.")

    assert turn.target_id == "mensagens_iniciais_009"
    assert "_progression_gate_blocked_target" not in turn.state.facts


def test_motor_e_reutilizavel_por_outro_card() -> None:
    document = {
        "psychological_state": {
            "engagement_deltas": {"engaged": {"trust": 2}}
        }
    }
    state = PilotState(trust=3)
    target = {
        "progression_gate": {
            "dimension": "trust",
            "min": 5,
            "fallback_target": "lia_holds_back",
        }
    }

    result = evaluate_progression_gate(document, state, target, "engaged")

    assert result.allowed is True
    assert result.actual_value == 5
