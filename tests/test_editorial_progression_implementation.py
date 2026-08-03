from __future__ import annotations

from pathlib import Path


PUBLIC_API = Path("services/editorial_progression.py")
IMPLEMENTATION = Path("services/editorial_progression_impl.py")
FINALIZATION = Path("services/editorial_turn_finalization.py")
REMOVED_HISTORICAL_ALIAS = Path("services/supermarket_script_v2.py")
REMOVED_SUPPORT = Path("services/editorial_progression_support.py")
REMOVED_LEGACY = Path("services/editorial_progression_legacy.py")


def test_api_publica_aponta_para_implementacao_editorial() -> None:
    source = PUBLIC_API.read_text(encoding="utf-8")

    assert "from services.editorial_progression_impl import" in source
    assert "from services.supermarket_script_v2 import" not in source
    assert "prepare_supermarket_script_v2" not in source
    assert "decide_supermarket_script_v2_turn" not in source


def test_progressao_ativa_usa_modulos_editoriais_definitivos() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")
    finalization = FINALIZATION.read_text(encoding="utf-8")

    assert "def decide_editorial_progression_turn(" in implementation
    assert "def prepare_editorial_script(" in implementation
    assert "from services.editorial_turn_finalization import" in implementation
    assert "from services import editorial_runtime_impl as runtime_impl" in implementation
    assert "runtime_impl.classify_user_message = classify_contextual_editorial_message" in implementation
    assert "services.pilot_supermarket" not in implementation
    assert "finalize_editorial_turn(" in implementation
    assert "editorial_progression_support" not in implementation
    assert "editorial_progression_legacy" not in implementation
    assert "supermarket_script_v2" not in implementation
    assert "automatic_followup" not in implementation
    assert "def finalize_editorial_turn(" in finalization
    assert not REMOVED_HISTORICAL_ALIAS.exists()
    assert not REMOVED_SUPPORT.exists()
    assert not REMOVED_LEGACY.exists()


def test_decisao_declarativa_e_exposta_pelo_modulo_ativo() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "from services.editorial_declared_decisions import" in implementation
    assert "decide_declared_special_turn(" in implementation
