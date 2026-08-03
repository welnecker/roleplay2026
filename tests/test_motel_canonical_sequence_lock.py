from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
)
from services.editorial_runtime import EditorialScript, EditorialState


def _script() -> EditorialScript:
    return prepare_editorial_script(
        EditorialScript(compile_editorial_document(load_source_document()))
    )


def test_card_declara_prefixo_de_continuidade_canonica() -> None:
    script = _script()
    policy = script.raw["organic_slack"]["strict_canonical"]

    assert policy["beat_prefixes"] == ["motel_"]
    assert policy["state_fact"] == "_strict_motel_canonical"
    assert policy["prompt_title"] == "CONTINUIDADE ESTRITA DO MOTEL"


def test_turno_do_motel_reage_e_traz_a_fala_canonica() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        EditorialState(node_id="motel_024"),
        "smack! hummm... tá saciada?",
    )

    assert turn.target_id == "motel_025"
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "true"
    assert turn.visible_fallback.startswith("Você me salvou, gostoso")
    assert "Responda primeiro" in turn.system_prompt
    assert "linha canônica" in turn.system_prompt
    assert "não acrescente nada depois" in turn.system_prompt.casefold()


def test_motel_nao_abre_folga_organica_que_atrasaria_a_sequencia() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        EditorialState(node_id="motel_025"),
        "você está completamente louca e eu quero mais",
    )

    assert turn.target_id == "motel_026"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.interstitial_turns == 0
    assert turn.state.facts["_organic_interstitial"] == "false"
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "true"


def test_fora_do_motel_modelo_continua_livre() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        EditorialState(node_id="video_007"),
        "sim, continua",
    )

    assert turn.target_id == "video_008"
    assert turn.state.facts["_force_fixed_response"] == "false"
    assert turn.state.facts["_strict_motel_canonical"] == "false"
