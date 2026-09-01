from __future__ import annotations

import json

from narrative_v2.models import StoryRun
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository


class _Table:
    def __init__(self, rows):
        self._rows = rows

    def records(self):
        return list(self._rows)


class _Interactions:
    def __init__(self, rows):
        self.table = _Table(rows)


class _Runs:
    def __init__(self, run: StoryRun):
        self._run = run
        self.runs = _Table([
            {
                "run_id": run.run_id,
                "credit_id": run.credit_id,
                "user_id": run.user_id,
                "package_id": run.package_id,
                "script_version": run.script_version,
                "current_block_id": run.current_block_id,
                "current_beat_id": run.current_beat_id,
                "status": run.status,
                "ending_code": run.ending_code,
                "state_version": run.state_version,
                "permanent_memory_ids_json": "[]",
                "started_at": run.started_at,
                "ended_at": run.ended_at,
                "updated_at": run.updated_at,
            }
        ])

    def _from_row(self, _row):
        return self._run


def _assistant(sequence: int, node: str, ending_code: str = "") -> dict[str, object]:
    return {
        "run_id": "run-1",
        "user_id": "user-1",
        "package_id": "roleplay2026.casada_frustrada",
        "role": "assistant",
        "sequence": sequence,
        "metadata_json": json.dumps(
            {"pilot_node": node, "pilot_ending_code": ending_code},
            ensure_ascii=False,
        ),
    }


def test_recupera_somente_falso_encerramento_apos_oi() -> None:
    run = StoryRun(
        run_id="run-1",
        credit_id="credit-1",
        user_id="user-1",
        package_id="roleplay2026.casada_frustrada",
        script_version="1",
        current_block_id="endings",
        current_beat_id="end_lost_interest",
        status="terminated",
        ending_code="mary_lost_interest",
        state_version=4,
        updated_at="2026-08-01T10:00:00Z",
    )
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    repository.runs = _Runs(run)
    repository.interactions = _Interactions(
        [
            _assistant(10, "mensagens_iniciais_001"),
            _assistant(12, "end_lost_interest", "mary_lost_interest"),
        ]
    )

    recovered = repository.get_resumable_completed_run(
        user_id="user-1",
        package_id="roleplay2026.casada_frustrada",
    )

    assert recovered is run


def test_nao_recupera_perda_de_interesse_em_outra_cena() -> None:
    run = StoryRun(
        run_id="run-1",
        credit_id="credit-1",
        user_id="user-1",
        package_id="roleplay2026.casada_frustrada",
        script_version="1",
        current_block_id="endings",
        current_beat_id="end_lost_interest",
        status="terminated",
        ending_code="mary_lost_interest",
        state_version=4,
        updated_at="2026-08-01T10:00:00Z",
    )
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    repository.runs = _Runs(run)
    repository.interactions = _Interactions(
        [
            _assistant(10, "reencontro_fila_004"),
            _assistant(12, "end_lost_interest", "mary_lost_interest"),
        ]
    )

    recovered = repository.get_resumable_completed_run(
        user_id="user-1",
        package_id="roleplay2026.casada_frustrada",
    )

    assert recovered is None


def test_conclusao_normal_nunca_e_retomavel() -> None:
    run = StoryRun(
        run_id="run-1",
        credit_id="credit-1",
        user_id="user-1",
        package_id="roleplay2026.casada_frustrada",
        script_version="1",
        current_block_id="capitulo1",
        current_beat_id="capitulo1_024",
        status="completed",
        ending_code="normal_completion",
        state_version=8,
        updated_at="2026-09-01T18:09:12Z",
    )
    repository = object.__new__(GoogleSheetsV2RuntimeRepository)
    repository.runs = _Runs(run)
    repository.interactions = _Interactions([])

    recovered = repository.get_resumable_completed_run(
        user_id="user-1",
        package_id="roleplay2026.casada_frustrada",
    )

    assert recovered is None
