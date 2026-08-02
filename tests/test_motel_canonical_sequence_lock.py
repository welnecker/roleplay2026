from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.pilot_supermarket import PilotScript, PilotState
from services.supermarket_script_v2 import (
    _is_strict_motel_beat,
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


def _script() -> PilotScript:
    return prepare_supermarket_script_v2(
        PilotScript(compile_editorial_document(load_source_document()))
    )


def test_todos_os_beats_numericos_do_motel_sao_canonicos() -> None:
    assert _is_strict_motel_beat("motel_001") is True
    assert _is_strict_motel_beat("motel_025") is True
    assert _is_strict_motel_beat("motel_999") is True
    assert _is_strict_motel_beat("video_008") is False
    assert _is_strict_motel_beat("motel_saida") is False


def test_turno_do_motel_forca_exatamente_a_fala_do_beat() -> None:
    turn = decide_supermarket_script_v2_turn(
        _script(),
        PilotState(node_id="motel_024"),
        "smack! fala o que mais você quer, safada...",
    )

    assert turn.target_id == "motel_025"
    assert turn.state.facts["_force_fixed_response"] == "true"
    assert turn.visible_fallback.startswith("Você me salvou, gostoso")


def test_motel_nao_abre_folga_organica_que_atrasaria_a_sequencia() -> None:
    turn = decide_supermarket_script_v2_turn(
        _script(),
        PilotState(node_id="motel_025"),
        "você está completamente louca e eu quero mais",
    )

    assert turn.target_id == "motel_026"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.interstitial_turns == 0
    assert turn.state.facts["_organic_interstitial"] == "false"
    assert turn.state.facts["_force_fixed_response"] == "true"


def test_fora_do_motel_modelo_continua_livre() -> None:
    turn = decide_supermarket_script_v2_turn(
        _script(),
        PilotState(node_id="video_007"),
        "sim, continua",
    )

    assert turn.target_id == "video_008"
    assert turn.state.facts["_force_fixed_response"] == "false"
