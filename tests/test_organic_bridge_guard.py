from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import (
    decide_editorial_progression_turn,
    editorial_followups_after,
    prepare_editorial_script,
)


def test_folga_organica_mantem_ponte_para_turno_posterior() -> None:
    script = prepare_editorial_script(
        PilotScript(compile_editorial_document(load_source_document()))
    )
    state = PilotState(node_id="late_night_008")

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Tchau, Mary... você é completamente louca.",
    )

    assert turn.state.facts["_organic_interstitial"] == "true"
    assert turn.target_id == "late_night_008"
    assert turn.state.pending_next_beat_id == "morning_bridge_001"
    assert editorial_followups_after(turn.target_id) == ()
