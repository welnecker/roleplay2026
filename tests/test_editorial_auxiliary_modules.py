from __future__ import annotations

import ast
from pathlib import Path


REMOVED_ALIASES = (
    Path("services/contact_exchange_pilot.py"),
    Path("services/alfredinho_call_pilot.py"),
    Path("services/private_thought_pilot.py"),
    Path("services/supermarket_intent_pilot.py"),
)
EDITORIAL_MODULES = (
    Path("services/editorial_contact_exchange.py"),
    Path("services/editorial_partner_call.py"),
    Path("services/editorial_private_thought.py"),
    Path("services/editorial_intent.py"),
)
REMOVED_IMPORTS = {
    "services.contact_exchange_pilot",
    "services.alfredinho_call_pilot",
    "services.private_thought_pilot",
    "services.supermarket_intent_pilot",
}


def test_aliases_auxiliares_foram_removidos() -> None:
    assert all(not path.exists() for path in REMOVED_ALIASES)


def test_modulos_editoriais_definitivos_existem() -> None:
    for path in EDITORIAL_MODULES:
        assert path.is_file()
        assert "_pilot.py" not in path.name


def test_codigo_nao_importa_aliases_auxiliares_removidos() -> None:
    for root in (Path("services"), Path("tests")):
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = {alias.name for alias in node.names}
                    assert imported.isdisjoint(REMOVED_IMPORTS), path
                elif isinstance(node, ast.ImportFrom):
                    assert node.module not in REMOVED_IMPORTS, path
