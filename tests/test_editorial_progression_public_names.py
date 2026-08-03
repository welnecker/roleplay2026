from __future__ import annotations

import ast
from pathlib import Path


REMOVED_IDENTIFIERS = {
    "automatic_followups_after",
    "classify_contextual_user_message",
    "clean_supermarket_script_v2_response",
    "decide_supermarket_script_v2_turn",
    "prepare_supermarket_script_v2",
    "render_automatic_followup_text",
    "state_after_automatic_followup",
}


def _used_identifiers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    return names | imported


def test_codigo_python_nao_usa_nomes_historicos_da_progressao() -> None:
    for root in (Path("services"), Path("tests")):
        for path in root.rglob("*.py"):
            if path == Path(__file__):
                continue
            assert not (_used_identifiers(path) & REMOVED_IDENTIFIERS), path


def test_api_e_implementacao_nao_declaram_nomes_historicos() -> None:
    for path in (
        Path("services/editorial_progression.py"),
        Path("services/editorial_progression_impl.py"),
    ):
        source = path.read_text(encoding="utf-8")
        for identifier in REMOVED_IDENTIFIERS:
            assert identifier not in source
