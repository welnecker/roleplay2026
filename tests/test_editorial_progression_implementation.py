from __future__ import annotations

from pathlib import Path


PUBLIC_API = Path("services/editorial_progression.py")
IMPLEMENTATION = Path("services/editorial_progression_impl.py")
LEGACY = Path("services/supermarket_script_v2.py")


def test_api_publica_aponta_para_implementacao_editorial() -> None:
    source = PUBLIC_API.read_text(encoding="utf-8")

    assert "from services.editorial_progression_impl import" in source
    assert "from services.supermarket_script_v2 import" not in source


def test_progressao_concreta_nao_fica_no_modulo_historico() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")
    legacy = LEGACY.read_text(encoding="utf-8")

    assert "def decide_supermarket_script_v2_turn(" in implementation
    assert "def prepare_supermarket_script_v2(" in implementation
    assert "def decide_supermarket_script_v2_turn(" not in legacy
    assert "def prepare_supermarket_script_v2(" not in legacy
    assert "sys.modules[__name__] = _editorial_progression_impl" in legacy
