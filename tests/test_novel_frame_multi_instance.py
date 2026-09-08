from __future__ import annotations

from types import SimpleNamespace

from platform_core.auth import AuthenticatedUser
from services.novel_frame_reveal_patch import _synchronize_remote_run
from services.runtime_persistence import RuntimePersistenceContext


class _Repository:
    def __init__(self, persisted, run) -> None:
        self.persisted = persisted
        self.run = run

    def list_interactions(self, *, run_id: str, limit: int = 500):
        assert run_id == self.run.run_id
        return list(self.persisted)

    def get_run(self, *, run_id: str):
        assert run_id == self.run.run_id
        return self.run


def _state(step: int) -> dict[str, object]:
    return {
        "step_index": step,
        "consumed_orders": list(range(1, step + 1)),
        "finished": False,
    }


def test_instancia_atrasada_adota_interacao_persistida_por_outro_dispositivo(monkeypatch) -> None:
    import persistence.factory as factory
    import services.novel_frame_reveal_patch as patch

    user = AuthenticatedUser(user_id="user_1", email="u@example.com", display_name="U")
    run = SimpleNamespace(run_id="run_1", state_version=2)
    context = RuntimePersistenceContext(
        package_id="roleplay2026.camilly",
        package_version="200",
        run=run,
        session=None,
        instance_id="desktop",
        next_sequence=2,
    )
    local = [
        {
            "role": "assistant",
            "sequence": 1,
            "editorial_node": "encontro_001",
            "_story_state": _state(1),
        }
    ]
    persisted = [
        *local,
        {
            "role": "assistant",
            "sequence": 2,
            "editorial_node": "encontro_002",
            "_story_state": _state(2),
        },
    ]
    repository = _Repository(persisted, run)
    prefix = "novel_v2:user_1:roleplay2026.camilly"
    fake_st = SimpleNamespace(
        secrets={},
        session_state={
            "authenticated_user": user,
            "selected_package_id": "roleplay2026.camilly",
            f"{prefix}:context": context,
            f"{prefix}:story_state": SimpleNamespace(step_index=1),
            f"{prefix}:messages": local,
        },
    )
    monkeypatch.setattr(patch, "st", fake_st)
    monkeypatch.setattr(factory, "build_google_sheets_repository", lambda _secrets: repository)

    assert _synchronize_remote_run() is True
    assert fake_st.session_state[f"{prefix}:context"].next_sequence == 3
    assert fake_st.session_state[f"{prefix}:story_state"].step_index == 2
    assert fake_st.session_state[f"{prefix}:messages"][-1]["editorial_node"] == "encontro_002"


def test_instancia_atualizada_nao_forca_sincronizacao(monkeypatch) -> None:
    import persistence.factory as factory
    import services.novel_frame_reveal_patch as patch

    user = AuthenticatedUser(user_id="user_1", email="u@example.com", display_name="U")
    run = SimpleNamespace(run_id="run_1", state_version=1)
    messages = [
        {
            "role": "assistant",
            "sequence": 1,
            "editorial_node": "encontro_001",
            "_story_state": _state(1),
        }
    ]
    context = RuntimePersistenceContext(
        package_id="roleplay2026.camilly",
        package_version="200",
        run=run,
        session=None,
        instance_id="desktop",
        next_sequence=2,
    )
    repository = _Repository(messages, run)
    prefix = "novel_v2:user_1:roleplay2026.camilly"
    fake_st = SimpleNamespace(
        secrets={},
        session_state={
            "authenticated_user": user,
            "selected_package_id": "roleplay2026.camilly",
            f"{prefix}:context": context,
            f"{prefix}:story_state": SimpleNamespace(step_index=1),
            f"{prefix}:messages": messages,
        },
    )
    monkeypatch.setattr(patch, "st", fake_st)
    monkeypatch.setattr(factory, "build_google_sheets_repository", lambda _secrets: repository)

    assert _synchronize_remote_run() is False
    assert fake_st.session_state[f"{prefix}:context"].next_sequence == 2
