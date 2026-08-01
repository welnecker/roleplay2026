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


def test_list_interactions_nao_corta_em_vinte_registros() -> None:
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    repository.interactions = _FakeInteractions(
        [
            {
                "run_id": "run_1",
                "sequence": index,
                "role": "assistant" if index % 2 == 0 else "user",
                "content": f"mensagem {index}",
                "metadata_json": "{}",
            }
            for index in range(1, 81)
        ]
    )

    messages = repository.list_interactions(run_id="run_1", limit=500)

    assert len(messages) == 80
    assert messages[0]["sequence"] == 1
    assert messages[-1]["sequence"] == 80


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
