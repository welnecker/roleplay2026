from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script


def test_fala_sexual_contextual_nao_encerra_historia() -> None:
    script = prepare_editorial_script(
        PilotScript(compile_editorial_document(load_source_document()))
    )
    state = PilotState(node_id="motel_006")

    turn = decide_editorial_progression_turn(
        script,
        state,
        "sim... ahhhh!!! você chupa igual uma vadia...",
    )

    assert turn.finished is False
    assert turn.run_status == "active"
    assert turn.ending_code == ""
    assert turn.target_id == "motel_006"
    assert turn.state.node_id == "motel_006"
    assert turn.state.pending_next_beat_id == "motel_007"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert "_organic_interstitial" not in turn.state.facts
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "true"
