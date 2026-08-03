from __future__ import annotations

import ast
from pathlib import Path


PUBLIC_RUNTIME = Path("services/editorial_runtime.py")
IMPLEMENTATION = Path("services/editorial_runtime_impl.py")
REMOVED_ALIAS = Path("services/pilot_supermarket.py")


def test_api_publica_depende_da_implementacao_editorial() -> None:
    source = PUBLIC_RUNTIME.read_text(encoding="utf-8")

    assert "from services.editorial_runtime_impl import" in source
    assert "from services.pilot_supermarket import" not in source


def test_implementacao_concreta_vive_no_runtime_editorial() -> None:
    implementation = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "class PilotState" in implementation
    assert "class PilotScript" in implementation
    assert "def decide_turn(" in implementation
    assert not REMOVED_ALIAS.exists()


def test_codigo_python_nao_importa_alias_pilot_removido() -> None:
    for root in (Path("services"), Path("tests")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module != "services.pilot_supermarket", str(path)
                elif isinstance(node, ast.Import):
                    assert all(
                        alias.name != "services.pilot_supermarket"
                        for alias in node.names
                    ), str(path)
