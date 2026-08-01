from narrative_v2.models import StoryRun
from platform_core.auth import AuthenticatedUser
from services import runtime_persistence


class FakeRuntimeRepository:
    def __init__(self, *, candidate: StoryRun | None, messages: list[dict[str, object]]) -> None:
        self.candidate = candidate
        self.messages = messages
        self.reactivated: StoryRun | None = None

    def get_resumable_completed_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        del user_id, package_id
        return self.candidate

    def list_interactions(self, *, run_id: str, limit: int) -> list[dict[str, object]]:
        del run_id, limit
        return list(self.messages)

    def reactivate_run(self, run: StoryRun) -> StoryRun:
        run.status = "active"
        run.ending_code = ""
        run.ended_at = ""
        self.reactivated = run
        return run


def _run() -> StoryRun:
    return StoryRun(
        run_id="run_1",
        credit_id="credit_1",
        user_id="user_1",
        package_id="roleplay2026.casada_frustrada",
        script_version="1.0.0",
        current_block_id="supermercado",
        current_beat_id="pontes_finais",
        status="completed",
        ending_code="normal_completion",
        state_version=9,
        ended_at="2026-07-31T23:00:00Z",
    )


def _messages(consumed_orders: list[int]) -> list[dict[str, object]]:
    return [
        {
            "role": "assistant",
            "content": "Última fala salva",
            "sequence": 12,
            "_story_state": {
                "step_index": len(consumed_orders),
                "consumed_orders": consumed_orders,
                "finished": True,
            },
        }
    ]


def test_reabre_mesma_run_quando_roteiro_ganhou_novos_movimentos(monkeypatch) -> None:
    repository = FakeRuntimeRepository(candidate=_run(), messages=_messages(list(range(1, 24))))
    user = AuthenticatedUser("user_1", "u@example.com", "Usuário")
    monkeypatch.setattr(runtime_persistence, "_current_story_max_order", lambda package_id: 61)
    monkeypatch.setattr(runtime_persistence, "clear_paid_access_cache", lambda **kwargs: None)

    run, state, messages = runtime_persistence._try_resume_completed_run(
        repository,  # type: ignore[arg-type]
        user=user,
        package_id="roleplay2026.casada_frustrada",
    )

    assert run is repository.reactivated
    assert run is not None and run.credit_id == "credit_1"
    assert run.status == "active"
    assert state.finished is False
    assert state.consumed_orders[-1] == 23
    assert messages[-1]["content"] == "Última fala salva"


def test_nao_reabre_quando_roteiro_realmente_terminou(monkeypatch) -> None:
    repository = FakeRuntimeRepository(candidate=_run(), messages=_messages(list(range(1, 62))))
    user = AuthenticatedUser("user_1", "u@example.com", "Usuário")
    monkeypatch.setattr(runtime_persistence, "_current_story_max_order", lambda package_id: 61)

    run, state, messages = runtime_persistence._try_resume_completed_run(
        repository,  # type: ignore[arg-type]
        user=user,
        package_id="roleplay2026.casada_frustrada",
    )

    assert run is None
    assert repository.reactivated is None
    assert state.finished is False
    assert messages == []
