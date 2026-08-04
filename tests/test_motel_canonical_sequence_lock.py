from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import decide_editorial_progression_turn, prepare_editorial_script
from services.editorial_runtime import EditorialScript, EditorialState


def _script() -> EditorialScript:
    return prepare_editorial_script(
        EditorialScript(compile_editorial_document(load_source_document()))
    )


def _assert_bridge(turn, *, origin: str, target: str) -> None:
    assert turn.target_id == origin
    assert turn.state.node_id == origin
    assert turn.state.pending_next_beat_id == target
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert turn.state.facts["_bridge_target_beat_id"] == target
    assert turn.state.facts["_organic_interstitial"] == "false"
    assert "FASE ESTRUTURAL: PONTE NARRATIVA" in turn.system_prompt


def test_card_declara_prefixo_de_continuidade_canonica() -> None:
    policy = _script().raw["runtime_policy"]["strict_canonical"]

    assert policy["beat_prefixes"] == ["motel_"]
    assert policy["state_fact"] == "_strict_motel_canonical"
    assert policy["prompt_title"] == "CONTINUIDADE ESTRITA DO MOTEL"


def test_turno_do_motel_reage_sem_executar_a_fala_canonica_seguinte() -> None:
    turn = decide_editorial_progression_turn(
        _script(), EditorialState(node_id="motel_024"), "smack! hummm... tá saciada?"
    )

    _assert_bridge(turn, origin="motel_024", target="motel_025")
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "true"
    assert "Você me salvou, gostoso" not in turn.visible_fallback
    assert "LINHA FUTURA PROIBIDA" in turn.system_prompt


def test_motel_usa_ponte_estrutural_sem_folga_organica() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        EditorialState(node_id="motel_025"),
        "você está completamente louca e eu quero mais",
    )

    _assert_bridge(turn, origin="motel_025", target="motel_026")
    assert turn.state.interstitial_turns == 0
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "true"


def test_fora_do_motel_tambem_usa_ponte_global() -> None:
    turn = decide_editorial_progression_turn(
        _script(), EditorialState(node_id="video_007"), "sim, continua"
    )

    _assert_bridge(turn, origin="video_007", target="video_008")
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "false"
