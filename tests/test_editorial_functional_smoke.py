from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

from packages.loader import discover_packages
from services.editorial_package_loader import compile_editorial_package
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime import EditorialState, editorial_opening_text


def _single_package(root: Path):
    packages, errors = discover_packages(root)
    assert errors == []
    assert len(packages) == 1
    return packages[0]


def _assert_package_runs(package_root: Path) -> None:
    package = _single_package(package_root)
    script = compile_editorial_package(package)

    opening = editorial_opening_text(script)
    assert opening.strip()
    assert script.first_beat_id in script.beats

    turn = decide_editorial_progression_turn(
        script,
        EditorialState(),
        "Olá, prazer em conhecer você.",
    )
    assert turn.target_id
    assert turn.visible_fallback.strip()
    assert turn.state.node_id


def test_card_instalado_compila_e_executa_primeiro_turno() -> None:
    _assert_package_runs(Path("installed_stories/casada_frustrada"))


def test_card_independente_compila_e_executa_primeiro_turno() -> None:
    _assert_package_runs(Path("tests/fixtures/editorial_cards/encontro_no_cafe"))


def test_entrypoint_reexecuta_runtime_ja_importado(monkeypatch) -> None:
    import services.editorial_player as entrypoint

    runtime = ModuleType("services.editorial_player_runtime")
    monkeypatch.setitem(sys.modules, "services.editorial_player_runtime", runtime)
    reloaded: list[ModuleType] = []

    def fake_reload(module: ModuleType) -> ModuleType:
        reloaded.append(module)
        return module

    monkeypatch.setattr(importlib, "reload", fake_reload)
    entrypoint.run_editorial_player()

    assert reloaded == [runtime]
