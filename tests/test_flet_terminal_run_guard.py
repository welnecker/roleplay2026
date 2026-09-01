from __future__ import annotations

from types import SimpleNamespace

from flet_api import terminal_run_guard as guard
from flet_api.runs import FletRunService, RunFrame


def _frame(*, finished: bool) -> RunFrame:
    return RunFrame(
        run_id="run_1",
        package_id="story_1",
        frame_id="frame_final" if finished else "frame_1",
        content="[QUADRO frame_final]\n[/QUADRO]" if finished else "[QUADRO frame_1]\n[/QUADRO]",
        image_url="",
        revealed_entries=1,
        entry_count=1,
        finished=finished,
    )


def _preserve_guard_state():
    cls = FletRunService
    with guard._CACHE_LOCK:
        cache = dict(guard._CACHE)
        guard._CACHE.clear()
    return cls.open, cls.advance, cls.reveal, guard._INSTALLED, cache


def _restore_guard_state(state) -> None:
    real_open, real_advance, real_reveal, real_installed, real_cache = state
    FletRunService.open = real_open
    FletRunService.advance = real_advance
    FletRunService.reveal = real_reveal
    guard._INSTALLED = real_installed
    with guard._CACHE_LOCK:
        guard._CACHE.clear()
        guard._CACHE.update(real_cache)


def test_repeated_terminal_advance_is_served_without_calling_runtime_again() -> None:
    cls = FletRunService
    saved = _preserve_guard_state()
    calls = {"advance": 0}

    def fake_open(self, *, account, package_id):
        return _frame(finished=False)

    def fake_reveal(self, *, account, package_id, expected_frame_id):
        return _frame(finished=True)

    def fake_advance(self, *, account, package_id, expected_frame_id, revealed_entries):
        calls["advance"] += 1
        return _frame(finished=True)

    try:
        cls.open = fake_open  # type: ignore[method-assign]
        cls.advance = fake_advance  # type: ignore[method-assign]
        cls.reveal = fake_reveal  # type: ignore[method-assign]
        guard._INSTALLED = False
        guard.install()

        service = object()
        account = SimpleNamespace(user_id="user_1")

        first = cls.advance(  # type: ignore[arg-type]
            service,
            account=account,
            package_id="story_1",
            expected_frame_id="frame_final",
            revealed_entries=1,
        )
        second = cls.advance(  # type: ignore[arg-type]
            service,
            account=account,
            package_id="story_1",
            expected_frame_id="frame_final",
            revealed_entries=1,
        )

        assert first.finished is True
        assert second is first
        assert calls["advance"] == 1
    finally:
        _restore_guard_state(saved)


def test_repeated_terminal_reveal_is_served_without_calling_runtime_again() -> None:
    cls = FletRunService
    saved = _preserve_guard_state()
    calls = {"reveal": 0}

    def fake_open(self, *, account, package_id):
        return _frame(finished=False)

    def fake_reveal(self, *, account, package_id, expected_frame_id):
        calls["reveal"] += 1
        return _frame(finished=True)

    def fake_advance(self, *, account, package_id, expected_frame_id, revealed_entries):
        return _frame(finished=True)

    try:
        cls.open = fake_open  # type: ignore[method-assign]
        cls.advance = fake_advance  # type: ignore[method-assign]
        cls.reveal = fake_reveal  # type: ignore[method-assign]
        guard._INSTALLED = False
        guard.install()

        service = object()
        account = SimpleNamespace(user_id="user_1")
        first = cls.reveal(  # type: ignore[arg-type]
            service,
            account=account,
            package_id="story_1",
            expected_frame_id="frame_final",
        )
        second = cls.reveal(  # type: ignore[arg-type]
            service,
            account=account,
            package_id="story_1",
            expected_frame_id="frame_final",
        )

        assert first.finished is True
        assert second is first
        assert calls["reveal"] == 1
    finally:
        _restore_guard_state(saved)


def test_opening_non_terminal_run_clears_previous_terminal_cache() -> None:
    cls = FletRunService
    saved = _preserve_guard_state()
    calls = {"advance": 0}

    def fake_open(self, *, account, package_id):
        return _frame(finished=False)

    def fake_reveal(self, *, account, package_id, expected_frame_id):
        return _frame(finished=True)

    def fake_advance(self, *, account, package_id, expected_frame_id, revealed_entries):
        calls["advance"] += 1
        return _frame(finished=True)

    try:
        cls.open = fake_open  # type: ignore[method-assign]
        cls.advance = fake_advance  # type: ignore[method-assign]
        cls.reveal = fake_reveal  # type: ignore[method-assign]
        guard._INSTALLED = False
        guard.install()

        service = object()
        account = SimpleNamespace(user_id="user_1")
        guard._remember("user_1", _frame(finished=True))

        cls.open(service, account=account, package_id="story_1")  # type: ignore[arg-type]
        cls.advance(  # type: ignore[arg-type]
            service,
            account=account,
            package_id="story_1",
            expected_frame_id="frame_final",
            revealed_entries=1,
        )

        assert calls["advance"] == 1
    finally:
        _restore_guard_state(saved)
