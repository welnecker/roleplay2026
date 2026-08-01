from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_script_v2 import (
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_supermarket_script_v2(PilotScript(compile_editorial_document(document)))


def test_opa_apos_primeira_mensagem_avanca_sem_encerrar() -> None:
    script = _script()
    state = PilotState(
        node_id="mensagens_iniciais_001",
        interest=5,
        desire=3,
        patience=4,
        facts={"active_interlocutor": "janio"},
    )

    turn = decide_supermarket_script_v2_turn(script, state, "Opa...")

    assert turn.finished is False
    assert turn.target_id == "mensagens_iniciais_002"
    assert "não consegui esperar" in turn.visible_fallback
    assert turn.state.node_id == "mensagens_iniciais_002"


def test_continuacao_executavel_nao_aponta_mais_para_end_pilot() -> None:
    script = _script()

    assert script.beats["mensagens_iniciais_001"]["on_user"]["engaged"] == "mensagens_iniciais_002"
    assert script.beats["mensagens_iniciais_001"]["on_user"]["minimal"] == "mensagens_iniciais_002"
    assert "video_025" in script.beats
    assert script.beats["video_025"]["on_user"]["engaged"] == "end_pilot"
