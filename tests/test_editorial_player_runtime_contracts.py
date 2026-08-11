from __future__ import annotations

from pathlib import Path


RUNTIME_PATH = (
    Path(__file__).resolve().parent.parent
    / "services"
    / "editorial_player_runtime.py"
)


def test_player_importa_apenas_apis_editoriais_publicas() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "from services.editorial_runtime import" in source
    assert "from services.editorial_progression import" in source
    assert "from services.editorial_diagnostics import" in source
    assert "from services.editorial_metadata import" in source
    assert "from services.editorial_response_evaluator import" in source
    assert "from services.editorial_transaction import" in source
    assert "from services.pilot_supermarket import" not in source
    assert "from services.pilot_diagnostics import" not in source
    assert "from services.supermarket_script_v2 import" not in source


def test_player_recupera_estado_pelo_contrato_retrocompativel() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "recover_editorial_state_payload(messages)" in source
    assert 'message.get("pilot_state")' not in source
    assert "EditorialState.from_dict(payload)" in source


def test_player_grava_metadados_editoriais_centralizados() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "metadata = build_editorial_metadata(" in source
    assert "followup_metadata = build_editorial_bridge_metadata(" in source
    assert '"pilot_state":' not in source
    assert '"pilot_node":' not in source
    assert '"editorial_state":' not in source


def test_player_usa_pipeline_editorial_transacional() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "def load_script(package_id: str) -> EditorialScript:" in source
    assert "decide_editorial_turn(script, editorial_state, user_text)" in source
    assert "prepare_pending_editorial_turn(script, editorial_state, proposed_turn)" in source
    assert "clean_editorial_model_response(raw_model_response, \"\")" in source
    assert "evaluate_deterministic_response(candidate, pending.context)" in source
    assert "parse_semantic_evaluation(semantic_raw)" in source
    assert "commit_editorial_turn(pending, assistant_text)" in source
    assert "editorial_opening_text(script)" in source
    assert "persist_opening_message(" in source
    assert "opening_editorial_state.node_id = script.first_beat_id" in source
    assert "build_editorial_turn_diagnostics(" in source
    assert "editorial_followups_after(turn.target_id)" in source
    assert "state_after_editorial_followup(" in source

    # O guard legado não pode voltar a substituir respostas por fala fixa.
    assert "finalize_editorial_model_response(" not in source
    assert "reaction_preserved_fallback_appended" not in source
    assert "fala segura usada" not in source
