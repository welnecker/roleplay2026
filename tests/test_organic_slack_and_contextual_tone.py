from pathlib import Path

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_script_v2 import (
    classify_contextual_user_message,
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_supermarket_script_v2(PilotScript(compile_editorial_document(document)))


def test_comentario_livre_nao_mistura_proxima_linha_do_roteiro() -> None:
    script = _script()
    state = PilotState(node_id="late_night_008", facts={"user_name": "Janio"})

    turn = decide_supermarket_script_v2_turn(
        script,
        state,
        "Tchau, Mary... você é louca...",
    )

    assert turn.target_id == "late_night_008"
    assert turn.state.pending_next_beat_id == "morning_bridge_001"
    assert turn.state.facts["_organic_interstitial"] == "true"
    assert "não misture a próxima linha canônica" in turn.system_prompt.casefold()
    assert "já amanheceu" not in turn.visible_fallback.casefold()


def test_turno_seguinte_retoma_o_beat_pendente() -> None:
    script = _script()
    state = PilotState(
        node_id="late_night_008",
        pending_next_beat_id="morning_bridge_001",
        interstitial_turns=1,
        facts={"_organic_interstitial": "true"},
    )

    turn = decide_supermarket_script_v2_turn(script, state, "Tá bom... até daqui a pouco.")

    assert turn.target_id == "morning_bridge_001"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts["_organic_interstitial"] == "false"


def test_pergunta_com_ressalva_recebe_resposta_organica_primeiro() -> None:
    script = _script()
    state = PilotState(node_id="late_night_004")

    turn = decide_supermarket_script_v2_turn(
        script,
        state,
        "Claro que eu quero, mas é perigoso... não quero morrer, né?",
    )

    assert turn.target_id == "late_night_004"
    assert turn.state.pending_next_beat_id == "late_night_005"
    assert "Sabe aquele motel" not in turn.visible_fallback


def test_linguagem_sexual_contextual_nao_e_hostilidade() -> None:
    assert (
        classify_contextual_user_message("sim... ahhhh! você chupa igual uma vadia...")
        == "engaged"
    )
    assert classify_contextual_user_message("você é uma vadia") == "hostile"


def test_delta_generator_nao_e_renderizado_por_expressao_solteira() -> None:
    source = Path("pages/2_Piloto_Supermercado.py").read_text(encoding="utf-8")

    assert "st.success(\"Cena concluída.\") if" not in source
    assert "if pilot_state.run_status == \"completed\":" in source
    assert "if not is_organic_interstitial:" in source
