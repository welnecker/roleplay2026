from __future__ import annotations

from dataclasses import replace

import pytest

from narrative_v2.models import StoryRun
from narrative_v2.repository import RuntimeConflictError
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository


def _run(*, version: int, block: str = "b1", beat: str = "x1") -> StoryRun:
    return StoryRun(
        run_id="run_1",
        credit_id="credit_1",
        user_id="user_1",
        package_id="pkg_1",
        script_version="1",
        current_block_id=block,
        current_beat_id=beat,
        status="active",
        state_version=version,
        started_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class _FakeTable:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def records(self) -> list[dict[str, object]]:
        return list(self._rows)


class _FakeInteractions:
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        self.table = _FakeTable(rows or [])
        self.appended: list[dict[str, object]] = []

    def append_interaction(self, **kwargs: object) -> None:
        self.appended.append(dict(kwargs))


class _FakeRuns:
    def __init__(self, current: StoryRun) -> None:
        self.current = current
        self.calls: list[tuple[int, str, str]] = []
        self._first = True

    def update_run(self, *, run: StoryRun, expected_version: int) -> StoryRun:
        self.calls.append((expected_version, run.current_block_id, run.current_beat_id))
        if self._first:
            self._first = False
            raise RuntimeConflictError("concorrência simulada")
        self.current = replace(
            run,
            state_version=expected_version + 1,
        )
        return self.current


class _FakeRunTable:
    def __init__(self, current: StoryRun) -> None:
        self.current = current

    def find(self, field: str, value: str):
        assert field == "run_id"
        assert value == self.current.run_id
        return 2, {
            "run_id": self.current.run_id,
            "credit_id": self.current.credit_id,
            "user_id": self.current.user_id,
            "package_id": self.current.package_id,
            "script_version": self.current.script_version,
            "current_block_id": self.current.current_block_id,
            "current_beat_id": self.current.current_beat_id,
            "status": self.current.status,
            "ending_code": self.current.ending_code,
            "state_version": self.current.state_version,
            "permanent_memory_ids_json": "[]",
            "started_at": self.current.started_at,
            "ended_at": self.current.ended_at,
            "updated_at": self.current.updated_at,
        }


def _repository() -> GoogleSheetsV2RuntimeRepository:
    return object.__new__(GoogleSheetsV2RuntimeRepository)


def test_update_run_progress_rele_run_e_repete_apenas_a_gravacao() -> None:
    repository = _repository()
    stale = _run(version=92)
    current = _run(version=93, block="b2", beat="x2")
    runs = _FakeRuns(current)
    runs.runs = _FakeRunTable(current)
    repository.runs = runs

    updated = repository.update_run_progress(
        run=stale,
        block_id="late_night",
        beat_id="late_night_003",
    )

    assert updated.state_version == 94
    assert updated.current_block_id == "late_night"
    assert updated.current_beat_id == "late_night_003"
    assert runs.calls == [
        (92, "late_night", "late_night_003"),
        (93, "late_night", "late_night_003"),
    ]


def test_update_run_progress_aceita_conflito_ja_resolvido() -> None:
    repository = _repository()
    stale = _run(version=92)
    current = _run(version=93, block="late_night", beat="late_night_003")
    runs = _FakeRuns(current)
    runs.runs = _FakeRunTable(current)
    repository.runs = runs

    updated = repository.update_run_progress(
        run=stale,
        block_id="late_night",
        beat_id="late_night_003",
    )

    assert updated is current
    assert runs.calls == [(92, "late_night", "late_night_003")]


def test_append_interaction_idempotente_nao_duplica_resposta_aprovada() -> None:
    repository = _repository()
    repository.interactions = _FakeInteractions(
        [
            {
                "run_id": "run_1",
                "sequence": 12,
                "role": "assistant",
                "content": "Resposta aprovada",
            }
        ]
    )

    repository.append_interaction(
        run_id="run_1",
        session_id="sess_1",
        user_id="user_1",
        package_id="pkg_1",
        role="assistant",
        speaker_id="mary",
        content="Resposta aprovada",
        sequence=12,
    )

    assert repository.interactions.appended == []


def test_append_interaction_rejeita_mesma_sequencia_com_conteudo_diferente() -> None:
    repository = _repository()
    repository.interactions = _FakeInteractions(
        [
            {
                "run_id": "run_1",
                "sequence": 12,
                "role": "assistant",
                "content": "Resposta original",
            }
        ]
    )

    with pytest.raises(RuntimeConflictError):
        repository.append_interaction(
            run_id="run_1",
            session_id="sess_1",
            user_id="user_1",
            package_id="pkg_1",
            role="assistant",
            speaker_id="mary",
            content="Resposta diferente",
            sequence=12,
        )
