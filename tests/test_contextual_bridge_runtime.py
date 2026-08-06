from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState


def _script():
    return prepare_editorial_script(
        PilotScript(compile_editorial_document(load_source_document()))
    )


def _continuing_state(node_id: str) -> PilotState:
    state = PilotState(
        node_id=node_id,
        recent_engagement=["engaged", "dismissive", "engaged"],
    )
    state.facts["_last_user_intent"] = "accept"
    state.facts["_contextual_route"] = "continue"
    return state


def test_short_continuation_advances_without_redundant_bridge() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        _continuing_state("motel_011"),
        "Continua... isso!!!",
    )

    assert turn.finished is False
    assert turn.run_status == "active"
    assert turn.ending_code == ""
    assert turn.target_id == "motel_012"
    assert turn.state.node_id == "motel_012"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts["_runtime_phase"] == "canonical"
    assert turn.state.facts["_qualified_ending_recovered"] == "true"


def test_substantive_contribution_creates_one_contextual_bridge() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        _continuing_state("motel_003"),
        "Quero sentir você reagindo enquanto eu continuo desse jeito",
    )

    assert turn.finished is False
    assert turn.target_id == "motel_003"
    assert turn.state.node_id == "motel_003"
    assert turn.state.pending_next_beat_id == "motel_004"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert turn.state.facts["_strict_motel_canonical"] == "true"
    assert "CONTRATO DE CONTINUIDADE DA PONTE" in turn.system_prompt
    assert "Preserve a intensidade" in turn.system_prompt
    assert "CONTINUIDADE ESTRITA DO MOTEL:" not in turn.system_prompt


def test_question_can_breathe_even_when_short() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        _continuing_state("motel_003"),
        "Assim?",
    )

    assert turn.finished is False
    assert turn.target_id == "motel_003"
    assert turn.state.pending_next_beat_id == "motel_004"
    assert turn.state.facts["_runtime_phase"] == "bridge"


def test_short_reply_outside_declared_scope_keeps_required_bridge() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        PilotState(node_id="late_night_004"),
        "sim",
    )

    assert turn.target_id == "late_night_004"
    assert turn.state.pending_next_beat_id == "late_night_005"
    assert turn.state.facts["_runtime_phase"] == "bridge"


def test_engine_implementation_is_not_tied_to_motel_ids() -> None:
    from pathlib import Path

    progression = Path("services/editorial_progression_impl.py").read_text(encoding="utf-8")
    finalization = Path("services/editorial_turn_finalization.py").read_text(encoding="utf-8")

    assert "motel_" not in progression
    assert "motel_" not in finalization
    assert "bridge_selection" in progression
    assert "bridge_continuity" in progression
    assert "qualified_endings" in progression
