from __future__ import annotations

from types import SimpleNamespace

from persistence import story_run_cache_guard as guard
from persistence import v2_google_sheets as v2_module


def test_empty_story_runs_cache_is_confirmed_authoritatively() -> None:
    cls = v2_module.GoogleSheetsStoryRunRepository
    real_method = cls.get_active_run
    real_installed = guard._INSTALLED

    class FakeTable:
        def __init__(self) -> None:
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

    try:
        # Simula exatamente o defeito observado: a consulta normal enxerga o
        # cache vazio, embora uma leitura autoritativa já encontre a run.
        cls.get_active_run = lambda self, *, user_id, package_id: None  # type: ignore[method-assign]
        guard._INSTALLED = False
        guard.install()

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
