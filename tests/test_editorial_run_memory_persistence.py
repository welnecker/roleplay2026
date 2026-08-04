from __future__ import annotations

from persistence.editorial_runtime_v2 import EditorialGoogleSheetsV2RuntimeRepository


class _FakeRuns:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def append_run_memory(
        self,
        *,
        run_id: str,
        memory_id: str,
        source_beat_id: str,
    ) -> None:
        self.calls.append(
            {
                "run_id": run_id,
                "memory_id": memory_id,
                "source_beat_id": source_beat_id,
            }
        )


def _repository() -> EditorialGoogleSheetsV2RuntimeRepository:
    repository = object.__new__(EditorialGoogleSheetsV2RuntimeRepository)
    repository.runs = _FakeRuns()
    return repository


def test_persiste_memorias_do_estado_editorial_canonico() -> None:
    repository = _repository()

    repository._persist_pending_memories(
        run_id="run_1",
        source_beat_id="beat_antigo",
        metadata={
            "editorial_node": "mensagens_iniciais_003",
            "editorial_state": {
                "facts": {
                    "_pending_memory_writes": (
                        "mary_confessed_attraction,first_private_messages"
                    )
                }
            },
        },
    )

    assert repository.runs.calls == [
        {
            "run_id": "run_1",
            "memory_id": "mary_confessed_attraction",
            "source_beat_id": "mensagens_iniciais_003",
        },
        {
            "run_id": "run_1",
            "memory_id": "first_private_messages",
            "source_beat_id": "mensagens_iniciais_003",
        },
    ]


def test_formato_pilot_permanece_apenas_para_compatibilidade() -> None:
    repository = _repository()

    repository._persist_pending_memories(
        run_id="run_legacy",
        source_beat_id="legacy_beat",
        metadata={
            "pilot_state": {
                "facts": {"_pending_memory_writes": "legacy_memory"}
            }
        },
    )

    assert repository.runs.calls == [
        {
            "run_id": "run_legacy",
            "memory_id": "legacy_memory",
            "source_beat_id": "legacy_beat",
        }
    ]


def test_estado_editorial_tem_precedencia_sobre_o_legado() -> None:
    repository = _repository()

    repository._persist_pending_memories(
        run_id="run_2",
        source_beat_id="fallback",
        metadata={
            "editorial_node": "beat_atual",
            "editorial_state": {
                "facts": {"_pending_memory_writes": "current_memory"}
            },
            "pilot_state": {
                "facts": {"_pending_memory_writes": "stale_memory"}
            },
        },
    )

    assert repository.runs.calls == [
        {
            "run_id": "run_2",
            "memory_id": "current_memory",
            "source_beat_id": "beat_atual",
        }
    ]
