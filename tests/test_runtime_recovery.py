import pytest

from narrative_v2.models import StoryRun
from narrative_v2.repository import RuntimeConflictError
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository
from services.runtime_persistence import _state_from_messages


class _FakeTable:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def records(self) -> list[dict[str, object]]:
        return list(self._rows)


class _FakeInteractions:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.table = _FakeTable(rows)


def _run(*, run_id: str = "run_1", user_id: str = "user_1", package_id: str = "story_1") -> StoryRun:
    return StoryRun(
        run_id=run_id,
        credit_id="credit_1",
        user_id=user_id,
        package_id=package_id,
        script_version="1",
        current_block_id="block_1",
        current_beat_id="beat_1",
    )


def _repository(rows: list[dict[str, object]], run: StoryRun) -> GoogleSheetsV2RuntimeRepository:
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    repository.interactions = _FakeInteractions(rows)
    repository.get_run = lambda *, run_id: run if run_id == run.run_id else None
    repository.list_run_memory_ids = lambda *, run_id: []
    return repository


def test_list_interactions_nao_corta_em_vinte_registros() -> None:
    run = _run()
    repository = _repository(
        [
            {
                "run_id": run.run_id,
                "user_id": run.user_id,
                "package_id": run.package_id,
                "sequence": index,
                "role": "assistant" if index % 2 == 0 else "user",
                "content": f"mensagem {index}",
                "metadata_json": "{}",
            }
            for index in range(1, 81)
        ],
        run,
    )

    messages = repository.list_interactions(run_id=run.run_id, limit=500)

    assert len(messages) == 80
    assert messages[0]["sequence"] == 1
    assert messages[-1]["sequence"] == 80


def test_list_interactions_falha_fechado_se_mesma_run_tiver_outro_usuario() -> None:
    run = _run()
    repository = _repository(
        [
            {
                "run_id": run.run_id,
                "user_id": run.user_id,
                "package_id": run.package_id,
                "sequence": 1,
                "role": "assistant",
                "content": "correta",
                "metadata_json": "{}",
            },
            {
                "run_id": run.run_id,
                "user_id": "user_outro",
                "package_id": run.package_id,
                "sequence": 2,
                "role": "assistant",
                "content": "não pode vazar",
                "metadata_json": "{}",
            },
        ],
        run,
    )

    with pytest.raises(RuntimeConflictError, match="proprietário incompatível"):
        repository.list_interactions(run_id=run.run_id)


def test_list_interactions_falha_fechado_se_mesma_run_tiver_outro_card() -> None:
    run = _run()
    repository = _repository(
        [
            {
                "run_id": run.run_id,
                "user_id": run.user_id,
                "package_id": "story_outro",
                "sequence": 1,
                "role": "assistant",
                "content": "não pode vazar",
                "metadata_json": "{}",
            }
        ],
        run,
    )

    with pytest.raises(RuntimeConflictError, match="proprietário incompatível"):
        repository.list_interactions(run_id=run.run_id)


def test_list_interactions_ignora_runs_de_outros_usuarios_e_cards() -> None:
    run = _run()
    repository = _repository(
        [
            {
                "run_id": run.run_id,
                "user_id": run.user_id,
                "package_id": run.package_id,
                "sequence": 1,
                "role": "assistant",
                "content": "história correta",
                "metadata_json": "{}",
            },
            {
                "run_id": "run_outro_usuario",
                "user_id": "user_outro",
                "package_id": run.package_id,
                "sequence": 1,
                "role": "assistant",
                "content": "outro usuário",
                "metadata_json": "{}",
            },
            {
                "run_id": "run_outro_card",
                "user_id": run.user_id,
                "package_id": "story_outro",
                "sequence": 1,
                "role": "assistant",
                "content": "outro card",
                "metadata_json": "{}",
            },
        ],
        run,
    )

    messages = repository.list_interactions(run_id=run.run_id)

    assert [message["content"] for message in messages] == ["história correta"]


def test_estado_e_recuperado_pela_maior_sequence() -> None:
    messages = [
        {
            "role": "assistant",
            "sequence": 20,
            "_story_state": {
                "step_index": 10,
                "consumed_orders": list(range(1, 11)),
                "finished": False,
            },
        },
        {
            "role": "assistant",
            "sequence": 8,
            "_story_state": {
                "step_index": 4,
                "consumed_orders": list(range(1, 5)),
                "finished": False,
            },
        },
    ]

    state = _state_from_messages(messages)

    assert state.step_index == 10
    assert state.consumed_orders[-1] == 10
