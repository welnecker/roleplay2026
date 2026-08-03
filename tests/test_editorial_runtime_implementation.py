from __future__ import annotations

from pathlib import Path


PUBLIC_RUNTIME = Path("services/editorial_runtime.py")
IMPLEMENTATION = Path("services/editorial_runtime_impl.py")
LEGACY_RUNTIME = Path("services/pilot_supermarket.py")


def test_api_publica_depende_da_implementacao_editorial() -> None:
    source = PUBLIC_RUNTIME.read_text(encoding="utf-8")

    assert "from services.editorial_runtime_impl import" in source
    assert "from services.pilot_supermarket import" not in source


def test_implementacao_concreta_nao_fica_no_modulo_piloto() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")
    legacy = LEGACY_RUNTIME.read_text(encoding="utf-8")

    assert "class PilotState" in implementation
    assert "class PilotScript" in implementation
    assert "def decide_turn(" in implementation
    assert "class PilotState" not in legacy
    assert "class PilotScript" not in legacy
    assert "def decide_turn(" not in legacy
    assert "from services import editorial_runtime_impl as _editorial_runtime_impl" in legacy
    assert "sys.modules[__name__] = _editorial_runtime_impl" in legacy
    assert "from services.editorial_runtime_impl import *" not in legacy
