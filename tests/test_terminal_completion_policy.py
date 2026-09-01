from __future__ import annotations

from types import SimpleNamespace

from flet_api import terminal_completion_policy as policy
from flet_api.runs import RunFrame


class FakeState:
    def __init__(self, finished: bool) -> None:
        self.finished = finished

    def copy(self):
        return FakeState(self.finished)


class FakeService:
    def __init__(self) -> None:
        self.secrets = {"test": True}

    def _generate(self, **kwargs):
        state = kwargs["state"].copy()
        state.finished = True
        policy.runs_module.persist_assistant_message(state=state)
        policy.runs_module.finish_active_run(status="completed")
        return object(), state, []

    def reveal(self, *, account, package_id, expected_frame_id):
        del account, expected_frame_id
        return RunFrame(
            run_id="run_1",
            package_id=package_id,
            frame_id="final",
            content="[QUADRO final]\n[/QUADRO]",
            image_url="",
            revealed_entries=2,
            entry_count=2,
            finished=False,
        )


def test_terminal_generation_stays_active_until_last_reveal(monkeypatch) -> None:
    saved_class = policy.FletRunService
    saved_persist = policy.runs_module.persist_assistant_message
    saved_finish = policy.runs_module.finish_active_run
    saved_installed = policy._INSTALLED
    persisted_finished: list[bool] = []
    generated_finish_calls: list[dict[str, object]] = []
    terminal_finish_calls: list[dict[str, object]] = []

    def fake_persist(*args, **kwargs):
        del args
        persisted_finished.append(bool(kwargs["state"].finished))
        return object()

    def fake_generated_finish(*args, **kwargs):
        del args
        generated_finish_calls.append(kwargs)
        return None

    def fake_terminal_finish(*args, **kwargs):
        del args
        terminal_finish_calls.append(kwargs)
        return None

    try:
        monkeypatch.setattr(policy, "FletRunService", FakeService)
        monkeypatch.setattr(policy, "_generation_is_terminal", lambda script, target_id: True)
        monkeypatch.setattr(policy, "_frame_is_terminal", lambda service, package_id, frame_id: True)
        monkeypatch.setattr(policy, "finish_active_run", fake_terminal_finish)
        policy.runs_module.persist_assistant_message = fake_persist
        policy.runs_module.finish_active_run = fake_generated_finish
        policy._INSTALLED = False
        policy.install()

        service = FakeService()
        _context, state, _messages = service._generate(
            script=object(),
            target_id="final",
            state=FakeState(False),
        )

        assert persisted_finished == [False]
        assert state.finished is False
        assert generated_finish_calls == []

        frame = service.reveal(
            account=SimpleNamespace(user_id="user_1"),
            package_id="story_1",
            expected_frame_id="final",
        )

        assert frame.finished is True
        assert terminal_finish_calls == [
            {
                "secrets": {"test": True},
                "user_id": "user_1",
                "package_id": "story_1",
                "status": "completed",
                "ending_code": "normal_completion",
            }
        ]
    finally:
        policy.FletRunService = saved_class
        policy.runs_module.persist_assistant_message = saved_persist
        policy.runs_module.finish_active_run = saved_finish
        policy._INSTALLED = saved_installed
