from __future__ import annotations

import ast
from pathlib import Path


REMOVED_MODULE = "services.pilot_diagnostics"
REMOVED_PATH = Path("services/pilot_diagnostics.py")
PUBLIC_PATH = Path("services/editorial_diagnostics.py")
IMPLEMENTATION_PATH = Path("services/editorial_diagnostics_impl.py")


def _imports_removed_module(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == REMOVED_MODULE for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == REMOVED_MODULE:
                return True
    return False


def test_diagnostico_possui_api_publica_e_implementacao_editorial() -> None:
    public = PUBLIC_PATH.read_text(encoding="utf-8")
    implementation = IMPLEMENTATION_PATH.read_text(encoding="utf-8")

    assert PUBLIC_PATH.is_file()
    assert IMPLEMENTATION_PATH.is_file()
    assert "services.editorial_diagnostics_impl" in public
    assert "class GuardedResponse" in implementation
    assert "def finalize_model_response" in implementation
    assert "def build_turn_diagnostics" in implementation


def test_fachada_pilot_diagnostics_foi_removida() -> None:
    assert not REMOVED_PATH.exists()
    assert REMOVED_MODULE not in PUBLIC_PATH.read_text(encoding="utf-8")


def test_codigo_ativo_e_testes_nao_importam_diagnostico_removido() -> None:
    for root in (Path("services"), Path("tests")):
        for path in root.rglob("*.py"):
            assert not _imports_removed_module(path), f"Import histórico em {path}"
