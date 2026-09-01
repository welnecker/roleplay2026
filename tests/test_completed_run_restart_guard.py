from types import SimpleNamespace

from flet_api import completed_run_restart_guard as guard


class FakeRepositoryClass:
    candidate = None

    def get_resumable_completed_run(self, *, user_id: str, package_id: str):
        del user_id, package_id
        return self.candidate


class FakeServiceClass:
    loads = []

    def _load(self, account, package_id):
        del account, package_id
        return self.loads.pop(0)


def _values(*, run=None, finished=False):
    return (
        object(),
        object(),
        object(),
        SimpleNamespace(run=run),
        SimpleNamespace(finished=finished),
        [],
        {},
    )


def test_normal_completion_is_never_resumable(monkeypatch) -> None:
    completed = SimpleNamespace(status="completed")
    FakeRepositoryClass.candidate = completed
    FakeServiceClass.loads = []

    monkeypatch.setattr(guard, "GoogleSheetsV2RuntimeRepository", FakeRepositoryClass)
    monkeypatch.setattr(guard, "FletRunService", FakeServiceClass)
    monkeypatch.setattr(guard, "_INSTALLED", False)

    guard.install()

    repository = FakeRepositoryClass()
    assert (
        repository.get_resumable_completed_run(
            user_id="user_1",
            package_id="roleplay2026.test",
        )
        is None
    )


def test_legacy_noncompleted_candidate_remains_resumable(monkeypatch) -> None:
    legacy = SimpleNamespace(status="terminated")

    class LegacyRepository:
        def get_resumable_completed_run(self, *, user_id: str, package_id: str):
            del user_id, package_id
            return legacy

    class Service:
        def _load(self, account, package_id):
            del account, package_id
            return _values()

    monkeypatch.setattr(guard, "GoogleSheetsV2RuntimeRepository", LegacyRepository)
    monkeypatch.setattr(guard, "FletRunService", Service)
    monkeypatch.setattr(guard, "_INSTALLED", False)

    guard.install()

    assert (
        LegacyRepository().get_resumable_completed_run(
            user_id="user_1",
            package_id="roleplay2026.test",
        )
        is legacy
    )


def test_stale_active_finished_run_is_closed_and_reloaded(monkeypatch) -> None:
    active = SimpleNamespace(status="active")
    fresh_values = _values(run=None, finished=False)

    class Repository:
        def get_resumable_completed_run(self, *, user_id: str, package_id: str):
            del user_id, package_id
            return None

    class Service:
        def __init__(self):
            self.secrets = {"test": True}
            table = SimpleNamespace(_records_cache=(9999999999.0, [{"run_id": "old"}]))
            self.repository = SimpleNamespace(runs=SimpleNamespace(runs=table))
            self.calls = 0

        def _load(self, account, package_id):
            del account, package_id
            self.calls += 1
            if self.calls == 1:
                return _values(run=active, finished=True)
            return fresh_values

    finished_calls = []

    def fake_finish_active_run(**kwargs):
        finished_calls.append(kwargs)
        return active

    monkeypatch.setattr(guard, "GoogleSheetsV2RuntimeRepository", Repository)
    monkeypatch.setattr(guard, "FletRunService", Service)
    monkeypatch.setattr(guard, "finish_active_run", fake_finish_active_run)
    monkeypatch.setattr(guard, "_INSTALLED", False)

    guard.install()

    service = Service()
    account = SimpleNamespace(user_id="user_1")
    result = service._load(account, "roleplay2026.test")

    assert result is fresh_values
    assert service.calls == 2
    assert service.repository.runs.runs._records_cache is None
    assert finished_calls == [
        {
            "secrets": {"test": True},
            "user_id": "user_1",
            "package_id": "roleplay2026.test",
            "status": "completed",
            "ending_code": "normal_completion",
        }
    ]
