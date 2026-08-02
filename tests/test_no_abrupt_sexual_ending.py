from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_script_v2 import (
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


def test_fala_sexual_contextual_nao_encerra_historia() -> None:
    script = prepare_supermarket_script_v2(
        PilotScript(compile_editorial_document(load_source_document()))
    )
    state = PilotState(node_id="motel_006")

    turn = decide_supermarket_script_v2_turn(
        script,
        state,
        "sim... ahhhh!!! você chupa igual uma vadia...",
    )

    assert turn.finished is False
    assert turn.run_status == "active"
    assert turn.ending_code == ""
    assert turn.target_id == "motel_007"
    assert turn.state.node_id == "motel_007"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.interstitial_turns == 0
    assert turn.state.facts["_organic_interstitial"] == "false"
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "true"
