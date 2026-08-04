import ast
from pathlib import Path

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_runtime_impl import PilotScript, PilotState
from services.editorial_progression import (
    classify_contextual_editorial_message,
    decide_editorial_progression_turn,
    prepare_editorial_script,
)


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_comentario_livre_nao_mistura_proxima_linha_do_roteiro() -> None:
    script = _script()
    state = PilotState(node_id="late_night_008", facts={"user_name": "Janio"})

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Tchau, Mary... você é louca...",
    )

    assert turn.target_id == "late_night_008"
    assert turn.state.pending_next_beat_id == "morning_bridge_001"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert turn.state.facts["_organic_interstitial"] == "false"
    assert "LINHA FUTURA PROIBIDA" in turn.system_prompt
    assert "já amanheceu" not in turn.visible_fallback.casefold()


def test_turno_seguinte_retoma_o_beat_pendente_da_ponte() -> None:
    script = _script()
    first = decide_editorial_progression_turn(
        script,
        PilotState(node_id="late_night_008"),
        "Tchau, Mary... você é louca...",
    )

    turn = decide_editorial_progression_turn(
        script,
        first.state,
        "Tá bom... até daqui a pouco.",
    )

    assert turn.target_id == "morning_bridge_001"
    assert turn.state.pending_next_beat_id == ""
    assert turn.state.facts["_runtime_phase"] == "canonical"
    assert turn.state.facts["_organic_interstitial"] == "false"


def test_pergunta_com_ressalva_recebe_ponte_sem_vazar_proxima_fala() -> None:
    script = _script()
    state = PilotState(node_id="late_night_004")

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Claro que eu quero, mas é perigoso... não quero morrer, né?",
    )

    assert turn.target_id == "late_night_004"
    assert turn.state.pending_next_beat_id == "late_night_005"
    assert turn.state.facts["_runtime_phase"] == "bridge"
    assert "Sabe aquele motel" not in turn.visible_fallback


def test_linguagem_sexual_contextual_nao_e_hostilidade() -> None:
    assert (
        classify_contextual_editorial_message("sim... ahhhh! você chupa igual uma vadia...")
        == "engaged"
    )
    assert classify_contextual_editorial_message("você é uma vadia") == "hostile"


def _is_streamlit_call(node: ast.AST, method: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "st"
        and node.func.attr == method
    )


def test_delta_generator_nao_e_renderizado_por_expressao_solteira() -> None:
    source = Path("services/editorial_player_runtime.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    success_in_ternary = any(
        isinstance(node, ast.IfExp)
        and any(_is_streamlit_call(child, "success") for child in ast.walk(node))
        for node in ast.walk(tree)
    )
    completed_status_block = any(
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and any(
            isinstance(child, ast.Attribute) and child.attr == "run_status"
            for child in ast.walk(node.test)
        )
        and any(
            isinstance(child, ast.Constant) and child.value == "completed"
            for child in ast.walk(node.test)
        )
        and any(_is_streamlit_call(child, "success") for child in ast.walk(node))
        for node in ast.walk(tree)
    )

    assert success_in_ternary is False
    assert completed_status_block is True
    assert "if not is_organic_interstitial:" in source
