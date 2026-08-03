from __future__ import annotations

from pathlib import Path


UI_COMPONENTS = Path("ui_components.py")
EDITORIAL_RUNTIME = Path("services/editorial_player_runtime.py")


def test_interface_limpa_apenas_namespace_editorial() -> None:
    source = UI_COMPONENTS.read_text(encoding="utf-8")

    assert 'prefix = f"editorial:{user_id}:{package_id}:"' in source
    assert 'f"pilot:{user_id}:{package_id}:"' not in source
    assert 'prefixes = (' not in source


def test_runtime_nao_reintroduz_namespace_pilot() -> None:
    source = EDITORIAL_RUNTIME.read_text(encoding="utf-8")

    assert 'prefix = f"editorial:{user_id}:{PACKAGE_ID}"' in source
    assert '"pilot:' not in source
