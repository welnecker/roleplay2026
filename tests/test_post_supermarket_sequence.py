from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
)


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_opa_apos_primeira_mensagem_avanca_sem_encerrar() -> None:
    script = _script()
    state = PilotState(
        node_id="mensagens_iniciais_001",
        interest=5,
        desire=3,
        patience=4,
        facts={"active_interlocutor": "janio"},
    )

    turn = decide_editorial_progression_turn(script, state, "Opa...")

    assert turn.finished is False
    assert turn.target_id == "mensagens_iniciais_002"
    assert "não consegui esperar" in turn.visible_fallback
    assert turn.state.node_id == "mensagens_iniciais_002"


def test_continuacao_executavel_segue_ate_a_historia_completa() -> None:
    script = _script()

    assert script.beats["mensagens_iniciais_001"]["on_user"]["engaged"] == "mensagens_iniciais_002"
    assert script.beats["mensagens_iniciais_001"]["on_user"]["minimal"] == "mensagens_iniciais_002"
    assert "video_025" in script.beats
    assert script.beats["video_025"]["on_user"]["engaged"] == "late_night_bridge_001"
    assert script.beats["late_night_008"]["on_user"]["engaged"] == "morning_bridge_001"
    assert script.beats["motel_039"]["on_user"]["engaged"] == "yard_motel_farewell_001"
    assert script.beats["yard_motel_farewell_004"]["on_user"]["engaged"] == "end_full_story"
