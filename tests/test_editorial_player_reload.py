from __future__ import annotations

import services.editorial_player as editorial_player


def test_executa_runtime_por_caminho_sem_importlib_reload(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def run_path(path: str, *, run_name: str):
        calls.append((path, run_name))
        return {"executed": True}

    monkeypatch.setattr(editorial_player.runpy, "run_path", run_path)

    result = editorial_player._execute_runtime()

    assert result == {"executed": True}
    assert calls == [
        (
            str(editorial_player._RUNTIME_PATH),
            "services.novel_player_runtime.__streamlit__",
        )
    ]


def test_cada_rerun_recebe_namespace_isolado(monkeypatch) -> None:
    namespaces: list[dict[str, object]] = []

    def run_path(_path: str, *, run_name: str):
        namespace = {"run_name": run_name, "ordinal": len(namespaces) + 1}
        namespaces.append(namespace)
        return namespace

    monkeypatch.setattr(editorial_player.runpy, "run_path", run_path)

    first = editorial_player._execute_runtime()
    second = editorial_player._execute_runtime()

    assert first is not second
    assert first["ordinal"] == 1
    assert second["ordinal"] == 2
