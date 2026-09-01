from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from narrative_v2.models import StoryRun
from roleplay.models import StoryState
from flet_api import runs as runs_module
from flet_api.runs import FletRunService
from services.runtime_persistence import RuntimePersistenceContext


def _run() -> StoryRun:
    return StoryRun(
        run_id="run_1",
        credit_id="credit_1",
        user_id="user_1",
        package_id="story_1",
        script_version="1",
        current_block_id="capitulo1",
        current_beat_id="capitulo1_023",
        status="active",
        state_version=7,
    )


def _terminal_message(*, revealed: int) -> dict[str, object]:
    return {
        "role": "assistant",
        "editorial_node": "capitulo1_024",
        "content": (
            "[QUADRO capitulo1_024]\n"
            "[DESCRIÇÃO]\nFim.\n"
            "[FALA mary|Mary]\n1\n"
            "[FALA mary|Mary]\n2\n"
            "[FALA professor|Professor]\n3\n"
            "[FALA mary|Mary]\n4\n"
            "[/QUADRO]"
        ),
        "flet_revealed_entries": revealed,
    }


def _service(*, persisted_reveal: int):
    service = object.__new__(FletRunService)
    context = RuntimePersistenceContext(
        package_id="story_1",
        package_version="1",
        run=_run(),
        instance_id="flet_user_1",
    )
    state = StoryState(step_index=24, consumed_orders=list(range(1, 25)), finished=False)
    messages = [_terminal_message(revealed=max(1, persisted_reveal - 1))]
    repository = SimpleNamespace(
        persist_frame_reveal=lambda **kwargs: persisted_reveal,
    )
    service.repository = repository
    service._lock = lambda *args, **kwargs: nullcontext()  # type: ignore[method-assign]
    service._load = lambda account, package_id: (  # type: ignore[method-assign]
        SimpleNamespace(),
        SimpleNamespace(),
        SimpleNamespace(),
        context,
        state,
        messages,
        {},
    )
    service._view = lambda package, script, context, state, messages: SimpleNamespace(  # type: ignore[method-assign]
        finished=state.finished,
        context=context,
    )
    return service, context, state


def test_terminal_frame_stays_active_until_last_reveal(monkeypatch) -> None:
    service, context, state = _service(persisted_reveal=3)
    finishes: list[str] = []
    monkeypatch.setattr(
        runs_module,
        "movement_from_script",
        lambda script, movement_id: SimpleNamespace(is_ending=True, block_id="capitulo1"),
    )
    service._finish_loaded_run = lambda **kwargs: finishes.append("finish") or context  # type: ignore[method-assign]

    result = service.reveal(
        account=SimpleNamespace(user_id="user_1"),
        package_id="story_1",
        expected_frame_id="capitulo1_024",
    )

    assert result.finished is False
    assert state.finished is False
    assert finishes == []


def test_last_terminal_reveal_completes_exactly_once(monkeypatch) -> None:
    service, context, state = _service(persisted_reveal=4)
    finishes: list[str] = []
    monkeypatch.setattr(
        runs_module,
        "movement_from_script",
        lambda script, movement_id: SimpleNamespace(is_ending=True, block_id="capitulo1"),
    )
    service._finish_loaded_run = lambda **kwargs: finishes.append("finish") or context  # type: ignore[method-assign]

    result = service.reveal(
        account=SimpleNamespace(user_id="user_1"),
        package_id="story_1",
        expected_frame_id="capitulo1_024",
    )

    assert result.finished is True
    assert state.finished is True
    assert finishes == ["finish"]


def test_finish_loaded_run_does_not_pre_read_story_runs(monkeypatch) -> None:
    service = object.__new__(FletRunService)
    run = _run()
    context = RuntimePersistenceContext(
        package_id="story_1",
        package_version="1",
        run=run,
    )

    class Runs:
        def __init__(self) -> None:
            self.updates = 0

        def update_run(self, *, run, expected_version):
            self.updates += 1
            assert expected_version == 7
            run.state_version = 8
            return run

    class Repository:
        def __init__(self) -> None:
            self.runs = Runs()
            self.active_reads = 0

        def get_active_run(self, **kwargs):
            self.active_reads += 1
            return None

        def get_run(self, **kwargs):
            raise AssertionError("get_run não deve ser usado sem conflito")

    repository = Repository()
    service.repository = repository
    monkeypatch.setattr(runs_module, "clear_paid_access_cache", lambda **kwargs: None)

    updated_context = service._finish_loaded_run(
        context=context,
        user_id="user_1",
        package_id="story_1",
        block_id="capitulo1",
        beat_id="capitulo1_024",
    )

    assert repository.runs.updates == 1
    assert repository.active_reads == 0
    assert updated_context.run is run
    assert run.status == "completed"
    assert run.ending_code == "normal_completion"
    assert run.current_beat_id == "capitulo1_024"
