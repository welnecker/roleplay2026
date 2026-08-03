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


def test_player_usa_nomes_publicos_do_runtime() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert "def load_script(package_id: str) -> EditorialScript:" in source
    assert "decide_editorial_turn(script, editorial_state, user_text)" in source
    assert "clean_editorial_model_response(" in source
    assert "editorial_opening_text(script)" in source
    assert "finalize_editorial_model_response(" in source
    assert "build_editorial_turn_diagnostics(" in source
    assert "editorial_followups_after(turn.target_id)" in source
    assert "state_after_editorial_followup(" in source
