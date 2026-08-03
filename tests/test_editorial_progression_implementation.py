from __future__ import annotations

from pathlib import Path


PUBLIC_API = Path("services/editorial_progression.py")
IMPLEMENTATION = Path("services/editorial_progression_impl.py")
SUPPORT = Path("services/editorial_progression_support.py")
HISTORICAL_ALIAS = Path("services/supermarket_script_v2.py")
REMOVED_LEGACY = Path("services/editorial_progression_legacy.py")


def test_api_publica_aponta_para_implementacao_editorial() -> None:
    source = PUBLIC_API.read_text(encoding="utf-8")

    assert "from services.editorial_progression_impl import" in source
    assert "from services.supermarket_script_v2 import" not in source


def test_progressao_ativa_usa_suporte_editorial_definitivo() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")
    support = SUPPORT.read_text(encoding="utf-8")
    historical = HISTORICAL_ALIAS.read_text(encoding="utf-8")

    assert "def decide_supermarket_script_v2_turn(" in implementation
    assert "from services import editorial_progression_support as _support" in implementation
    assert "editorial_progression_legacy" not in implementation
    assert "def prepare_supermarket_script_v2(" in support
    assert "def decide_supermarket_script_v2_turn(" not in historical
    assert "def prepare_supermarket_script_v2(" not in historical
    assert "sys.modules[__name__] = _editorial_progression_impl" in historical
    assert not REMOVED_LEGACY.exists()


def test_decisao_declarativa_e_exposta_pelo_modulo_ativo() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "from services.editorial_declared_decisions import" in implementation
    assert "decide_declared_special_turn(" in implementation
