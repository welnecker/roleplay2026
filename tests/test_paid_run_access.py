from __future__ import annotations

from dataclasses import dataclass

from narrative_v2.models import RunCredit, StoryRun
from services import paid_run_access


@dataclass
class FakeCredits:
    credit: RunCredit | None = None

    def get_available_credit(self, *, user_id: str, package_id: str) -> RunCredit | None:
        return self.credit


@dataclass
class FakeRuns:
    run: StoryRun | None = None
    updated: StoryRun | None = None

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        return self.run if self.run and self.run.status == "active" else None

    def update_run(self, *, run: StoryRun, expected_version: int) -> StoryRun:
        assert expected_version == 1
        run.state_version = 2
        self.updated = run
        return run


class ConcurrentFakeRuns:
    def __init__(self) -> None:
        self.read_count = 0
        self.update_count = 0
        self.updated: StoryRun | None = None

    @staticmethod
    def _run(version: int) -> StoryRun:
        return StoryRun(
            run_id="run_1",
            credit_id="credit_1",
            user_id="user_1",
            package_id="story_1",
            script_version="1.0.0",
            current_block_id="block_1",
            current_beat_id="beat_1",
            state_version=version,
        )

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun:
        self.read_count += 1
        return self._run(1 if self.read_count == 1 else 3)

    def update_run(self, *, run: StoryRun, expected_version: int) -> StoryRun:
        self.update_count += 1
        if self.update_count == 1:
            assert expected_version == 1
            raise RuntimeError(
                "Versão concorrente na run run_1: esperada=1, atual=3."
            )
        assert expected_version == 3
        run.state_version = 4
        self.updated = run
        return run


@dataclass
class FakeRepositories:
    credits: FakeCredits
    runs: object


def _clear_caches() -> None:
    paid_run_access._repository_cache.clear()
    paid_run_access._access_cache.clear()


def test_credit_available_libera_inicio(monkeypatch) -> None:
    _clear_caches()
    repositories = FakeRepositories(
        credits=FakeCredits(
            RunCredit(
                credit_id="credit_1",
                user_id="user_1",
                package_id="story_1",
                payment_id="pay_1",
                status="available",
            )
        ),
        runs=FakeRuns(),
    )
    monkeypatch.setattr(
        paid_run_access,
        "build_v2_narrative_repositories",
        lambda secrets: repositories,
    )

    access = paid_run_access.get_paid_run_access(
        secrets={},
        user_id="user_1",
        package_id="story_1",
    )

    assert access.state == "available"
    assert access.allowed is True
    _clear_caches()


def test_run_encerrada_remove_acesso(monkeypatch) -> None:
    _clear_caches()
    run = StoryRun(
        run_id="run_1",
        credit_id="credit_1",
        user_id="user_1",
        package_id="story_1",
        script_version="1.0.0",
        current_block_id="block_1",
        current_beat_id="beat_1",
    )
    repositories = FakeRepositories(credits=FakeCredits(), runs=FakeRuns(run))
    monkeypatch.setattr(
        paid_run_access,
        "build_v2_narrative_repositories",
        lambda secrets: repositories,
    )

    finished = paid_run_access.finish_active_run(
        secrets={},
        user_id="user_1",
        package_id="story_1",
        status="terminated",
        ending_code="user_abandoned",
    )
    access = paid_run_access.get_paid_run_access(
        secrets={},
        user_id="user_1",
        package_id="story_1",
    )

    assert finished is not None
    assert finished.status == "terminated"
    assert finished.ending_code == "user_abandoned"
    assert finished.ended_at
    assert access.state == "locked"
    assert access.allowed is False
    _clear_caches()


def test_encerramento_recarrega_run_apos_versao_concorrente(monkeypatch) -> None:
    _clear_caches()
    runs = ConcurrentFakeRuns()
    repositories = FakeRepositories(credits=FakeCredits(), runs=runs)
    monkeypatch.setattr(
        paid_run_access,
        "build_v2_narrative_repositories",
        lambda secrets: repositories,
    )

    finished = paid_run_access.finish_active_run(
        secrets={},
        user_id="user_1",
        package_id="story_1",
        status="completed",
        ending_code="normal_completion",
    )

    assert finished is not None
    assert finished.status == "completed"
    assert finished.ending_code == "normal_completion"
    assert finished.state_version == 4
    assert runs.read_count == 2
    assert runs.update_count == 2
    _clear_caches()
