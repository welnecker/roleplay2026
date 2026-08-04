from __future__ import annotations

from contextvars import Context

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_followups import (
    editorial_followups_after,
    state_after_editorial_followup,
)
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _script() -> PilotScript:
    return prepare_editorial_script(
        PilotScript(compile_editorial_document(load_source_document()))
    )


def test_rerun_reativa_followup_temporal_do_roteiro_em_cache() -> None:
    script = _script()

    def execute_in_new_context():
        turn = decide_editorial_progression_turn(
            script,
            PilotState(node_id="encontro_acidental_006"),
            "Tchau...",
        )
        return turn, editorial_followups_after(turn.target_id)

    turn, followups = Context().run(execute_in_new_context)

    assert turn.target_id == "encontro_acidental_006"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert turn.state.pending_next_beat_id == "reencontro_fila_001"
    assert len(followups) == 1

    followup = followups[0]
    assert followup["target_id"] == "reencontro_fila_001"
    assert "ALGUM TEMPO DEPOIS" in followup["text"]
    assert "SUPERMERCADO FILA" in followup["text"]
    assert "Olha você de novo" in followup["text"]


def test_followup_temporal_consume_a_ponte_sem_nova_fala_do_usuario() -> None:
    script = _script()
    turn = decide_editorial_progression_turn(
        script,
        PilotState(node_id="encontro_acidental_006"),
        "Tchau...",
    )
    followup = editorial_followups_after(turn.target_id, script=script)[0]

    updated = state_after_editorial_followup(turn.state, followup)

    assert updated.node_id == "reencontro_fila_001"
    assert updated.pending_next_beat_id == ""
    assert updated.facts["_runtime_phase"] == "canonical"
    assert "_bridge_origin_beat_id" not in updated.facts
    assert "_bridge_target_beat_id" not in updated.facts
    assert updated.facts["_scene_location"] == "supermercado_fila"
