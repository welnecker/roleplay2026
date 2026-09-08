from __future__ import annotations

from types import SimpleNamespace

from services import novel_run_version_guard as guard


class FakeScriptRepository:
    def __init__(self, rows):
        self.rows = rows

    def _records(self, name: str):
        assert name == "ROTEIROS"
        return list(self.rows)


class FakeRuntimeRepository:
    def __init__(self, active_run=None):
        self.active_run = active_run

    def get_active_run(self, *, user_id: str, package_id: str):
        return self.active_run


def test_rows_for_version_isolates_package_and_script_version() -> None:
    repository = FakeScriptRepository(
        [
            {
                "package_id": "roleplay2026.alpha",
                "script_version": "100",
                "line_id": "b",
                "order": 20,
                "status": "active",
            },
            {
                "package_id": "roleplay2026.alpha",
                "script_version": "200",
                "line_id": "wrong-version",
                "order": 5,
                "status": "active",
            },
            {
                "package_id": "roleplay2026.beta",
                "script_version": "100",
                "line_id": "wrong-package",
                "order": 5,
                "status": "active",
            },
            {
                "package_id": "roleplay2026.alpha",
                "script_version": "100",
                "line_id": "disabled",
                "order": 1,
                "status": "inactive",
            },
            {
                "package_id": "roleplay2026.alpha",
                "script_version": "100",
                "line_id": "a",
                "order": 10,
                "status": "active",
            },
        ]
    )

    rows = guard._rows_for_version(
        repository,
        package_id="roleplay2026.alpha",
        script_version="100",
    )

    assert [row["line_id"] for row in rows] == ["a", "b"]


def test_completed_run_is_not_reactivated(monkeypatch) -> None:
    calls = []

    def original(repository, **kwargs):
        calls.append(kwargs)
        return "context", SimpleNamespace(), []

    monkeypatch.setattr(guard, "_original_open_persistent_runtime", original)
    repository = FakeRuntimeRepository(active_run=None)
    user = SimpleNamespace(user_id="u1")

    guard._open_persistent_runtime_without_completed_reactivation(
        repository,
        user=user,
        package_id="roleplay2026.alpha",
        package_version="200",
        restart=False,
        instance_id="test",
    )

    assert calls[0]["restart"] is True


def test_active_run_is_resumed_only_with_matching_version(monkeypatch) -> None:
    calls = []

    def original(repository, **kwargs):
        calls.append(kwargs)
        return "context", SimpleNamespace(), []

    monkeypatch.setattr(guard, "_original_open_persistent_runtime", original)
    active = SimpleNamespace(script_version="100")
    repository = FakeRuntimeRepository(active_run=active)
    user = SimpleNamespace(user_id="u1")

    guard._open_persistent_runtime_without_completed_reactivation(
        repository,
        user=user,
        package_id="roleplay2026.alpha",
        package_version="100",
        restart=False,
        instance_id="test",
    )

    assert calls[0]["restart"] is False


def test_active_run_rejects_mixed_script_version(monkeypatch) -> None:
    monkeypatch.setattr(
        guard,
        "_original_open_persistent_runtime",
        lambda *args, **kwargs: ("context", SimpleNamespace(), []),
    )
    repository = FakeRuntimeRepository(active_run=SimpleNamespace(script_version="100"))
    user = SimpleNamespace(user_id="u1")

    try:
        guard._open_persistent_runtime_without_completed_reactivation(
            repository,
            user=user,
            package_id="roleplay2026.alpha",
            package_version="200",
            restart=False,
            instance_id="test",
        )
    except RuntimeError as exc:
        assert "versão diferente" in str(exc)
    else:
        raise AssertionError("Mistura de script_version deveria ser rejeitada")
