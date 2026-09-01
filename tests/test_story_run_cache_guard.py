from __future__ import annotations

from time import monotonic
from types import SimpleNamespace

from persistence import story_run_cache_guard as guard
from persistence import v2_google_sheets as v2_module


def _install_guard_over_fake_original(fake_original):
    cls = v2_module.GoogleSheetsStoryRunRepository
    real_method = cls.get_active_run
    real_installed = guard._INSTALLED
    cls.get_active_run = fake_original  # type: ignore[method-assign]
    guard._INSTALLED = False
    guard.install()
    return cls, real_method, real_installed


def test_empty_story_runs_cache_is_confirmed_authoritatively() -> None:
    class FakeTable:
        def __init__(self) -> None:
            # Simula o caso observado em produção: uma leitura anterior deixou
            # um cache vazio ainda válido, mas outra camada criou a run depois.
            self._records_cache = (monotonic() + 60.0, [])
            self.calls: list[tuple[bool, bool]] = []

        def records(
            self,
            *,
            force_refresh: bool = False,
            allow_stale_on_quota: bool = True,
        ) -> list[dict[str, object]]:
            self.calls.append((force_refresh, allow_stale_on_quota))
            if not force_refresh:
                return []
            return [
                {
                    "run_id": "run_1",
                    "user_id": "user_1",
                    "package_id": "story_1",
                    "status": "active",
                    "updated_at": "2026-08-31T20:00:00Z",
                }
            ]

    class FakeRepo:
        def __init__(self) -> None:
            self.runs = FakeTable()

        @staticmethod
        def _from_row(row: dict[str, object]) -> SimpleNamespace:
            return SimpleNamespace(**row)

    cls, real_method, real_installed = _install_guard_over_fake_original(
        lambda self, *, user_id, package_id: None
    )
    try:
        fake = FakeRepo()
        result = cls.get_active_run(  # type: ignore[arg-type]
            fake,
            user_id="user_1",
            package_id="story_1",
        )

        assert result is not None
        assert result.run_id == "run_1"
        assert fake.runs.calls == [(True, False)]
    finally:
        cls.get_active_run = real_method
        guard._INSTALLED = real_installed


def test_fresh_empty_read_is_not_immediately_read_again() -> None:
    class FakeTable:
        def __init__(self) -> None:
            self._records_cache = None
            self.calls: list[tuple[bool, bool]] = []

        def records(
            self,
            *,
            force_refresh: bool = False,
            allow_stale_on_quota: bool = True,
        ) -> list[dict[str, object]]:
            self.calls.append((force_refresh, allow_stale_on_quota))
            return []

    class FakeRepo:
        def __init__(self) -> None:
            self.runs = FakeTable()

    def fresh_read(self, *, user_id, package_id):
        # O método original acabou de consultar o Google e armazenou um cache
        # vazio fresco. O guard não deve repetir a mesma leitura imediatamente.
        self.runs._records_cache = (monotonic() + 60.0, [])
        return None

    cls, real_method, real_installed = _install_guard_over_fake_original(fresh_read)
    try:
        fake = FakeRepo()
        result = cls.get_active_run(  # type: ignore[arg-type]
            fake,
            user_id="user_1",
            package_id="story_1",
        )

        assert result is None
        assert fake.runs.calls == []
    finally:
        cls.get_active_run = real_method
        guard._INSTALLED = real_installed
