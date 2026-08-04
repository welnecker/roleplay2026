from __future__ import annotations

import sys
from types import ModuleType

import services.editorial_player as editorial_player


def test_importa_runtime_quando_ainda_nao_foi_carregado(monkeypatch) -> None:
    imported = ModuleType(editorial_player._RUNTIME_MODULE)
    monkeypatch.delitem(sys.modules, editorial_player._RUNTIME_MODULE, raising=False)
    monkeypatch.setattr(
        editorial_player.importlib,
        "import_module",
        lambda name: imported,
    )

    result = editorial_player._load_or_reload_runtime()

    assert result is imported


def test_reimporta_quando_refresh_remove_modulo(monkeypatch) -> None:
    stale = ModuleType(editorial_player._RUNTIME_MODULE)
    imported = ModuleType(editorial_player._RUNTIME_MODULE)
    monkeypatch.setitem(sys.modules, editorial_player._RUNTIME_MODULE, stale)

    def refresh(_loaded: ModuleType) -> None:
        sys.modules.pop(editorial_player._RUNTIME_MODULE, None)

    monkeypatch.setattr(editorial_player, "refresh_loaded_editorial_script_cache", refresh)
    monkeypatch.setattr(
        editorial_player.importlib,
        "import_module",
        lambda name: imported,
    )
    monkeypatch.setattr(
        editorial_player.importlib,
        "reload",
        lambda module: (_ for _ in ()).throw(AssertionError("reload não deveria ser chamado")),
    )

    result = editorial_player._load_or_reload_runtime()

    assert result is imported


def test_recarrega_instancia_atualmente_registrada(monkeypatch) -> None:
    stale = ModuleType(editorial_player._RUNTIME_MODULE)
    current = ModuleType(editorial_player._RUNTIME_MODULE)
    reloaded = ModuleType(editorial_player._RUNTIME_MODULE)
    monkeypatch.setitem(sys.modules, editorial_player._RUNTIME_MODULE, stale)

    def refresh(_loaded: ModuleType) -> None:
        sys.modules[editorial_player._RUNTIME_MODULE] = current

    seen: list[ModuleType] = []

    def reload(module: ModuleType) -> ModuleType:
        seen.append(module)
        return reloaded

    monkeypatch.setattr(editorial_player, "refresh_loaded_editorial_script_cache", refresh)
    monkeypatch.setattr(editorial_player.importlib, "reload", reload)

    result = editorial_player._load_or_reload_runtime()

    assert seen == [current]
    assert result is reloaded


def test_reimporta_quando_modulo_some_durante_reload(monkeypatch) -> None:
    registered = ModuleType(editorial_player._RUNTIME_MODULE)
    imported = ModuleType(editorial_player._RUNTIME_MODULE)
    monkeypatch.setitem(sys.modules, editorial_player._RUNTIME_MODULE, registered)
    monkeypatch.setattr(
        editorial_player,
        "refresh_loaded_editorial_script_cache",
        lambda _loaded: None,
    )

    def reload(_module: ModuleType) -> ModuleType:
        sys.modules.pop(editorial_player._RUNTIME_MODULE, None)
        raise ImportError(
            f"module {editorial_player._RUNTIME_MODULE!r} not in sys.modules"
        )

    monkeypatch.setattr(editorial_player.importlib, "reload", reload)
    monkeypatch.setattr(
        editorial_player.importlib,
        "import_module",
        lambda name: imported,
    )

    result = editorial_player._load_or_reload_runtime()

    assert result is imported
