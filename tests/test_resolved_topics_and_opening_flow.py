from pathlib import Path

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_resolved_topics import resolved_topic_ids


def _script():
    return prepare_editorial_script(
        PilotScript(compile_editorial_document(load_source_document()))
    )


def test_leaving_topic_beat_marks_subject_as_resolved_before_bridge() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        PilotState(node_id="encontro_acidental_002"),
        "Não, foi só um susto. E você está bem?",
    )

    assert turn.finished is False
    assert turn.target_id == "encontro_acidental_002"
    assert turn.state.pending_next_beat_id == "encontro_acidental_003"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert resolved_topic_ids(turn.state) == ["physical_wellbeing_after_accident"]
    assert "ASSUNTOS JÁ RESOLVIDOS — NÃO REABRIR" in turn.system_prompt
    assert "não peça nova confirmação" in turn.system_prompt


def test_next_opening_beat_changes_subject_instead_of_checking_again() -> None:
    script = _script()
    beat = script.beats["encontro_acidental_003"]

    assert "parece familiar" in str(beat["objective"]).casefold()
    dialogue = next(unit for unit in beat["units"] if unit.get("kind") == "dialogue")
    anchor = str(dialogue.get("anchor", "")).casefold()
    assert "rosto não me é estranho" in anchor
    assert "machuc" not in anchor
    assert "doendo" not in anchor
    assert "tudo bem mesmo" not in anchor


def test_resolved_topic_guard_survives_bridge_release() -> None:
    script = _script()
    bridge = decide_editorial_progression_turn(
        script,
        PilotState(node_id="encontro_acidental_002"),
        "Tudo certo, não se preocupe.",
    )
    canonical = decide_editorial_progression_turn(
        script,
        bridge.state,
        "Seu rosto também me parece familiar.",
    )

    assert canonical.target_id == "encontro_acidental_003"
    assert resolved_topic_ids(canonical.state) == ["physical_wellbeing_after_accident"]
    assert "ASSUNTOS JÁ RESOLVIDOS — NÃO REABRIR" in canonical.system_prompt


def test_topic_resolution_engine_has_no_card_specific_ids() -> None:
    source = Path("services/editorial_resolved_topics.py").read_text(encoding="utf-8")

    assert "encontro_acidental" not in source
    assert "physical_wellbeing_after_accident" not in source
    assert "resolve_topic_on_exit" in source
    assert "_resolved_topic_ids" in source
