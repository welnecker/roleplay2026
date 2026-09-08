from __future__ import annotations

from typing import Any

import pytest
from gspread.exceptions import APIError
from requests import Response

from narrative_v2.models import RunCredit
from narrative_v2.repository import RuntimeConflictError
from persistence.v2_google_sheets import (
    _SheetTable,
    GoogleSheetsNarrativeInteractionRepository,
    GoogleSheetsStoryCreditRepository,
    GoogleSheetsStoryRunRepository,
)
from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository
from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.google_sheets_retry import GoogleSheetsTemporarilyUnavailable
from persistence import v2_google_sheets
from persistence.v2_schemas import ACCOUNTS_BILLING_SCHEMAS, RUNTIME_SCHEMAS


class FakeWorksheet:
    def __init__(self, title: str, headers: tuple[str, ...]) -> None:
        self.title = title
        self.rows: list[list[Any]] = [list(headers)]
        self.header_reads = 0
        self.record_reads = 0
        self.read_error: Exception | None = None

    def row_values(self, row_number: int) -> list[Any]:
        self.header_reads += 1
        return list(self.rows[row_number - 1]) if row_number <= len(self.rows) else []

    def get_all_records(self, default_blank: str = "") -> list[dict[str, Any]]:
        self.record_reads += 1
        if self.read_error is not None:
            raise self.read_error
        headers = self.rows[0]
        return [
            {
                str(header): row[index] if index < len(row) else default_blank
                for index, header in enumerate(headers)
            }
            for row in self.rows[1:]
        ]

    def append_row(self, values: list[Any], value_input_option: str = "RAW") -> None:
        self.rows.append(list(values))

    def update(
        self,
        *,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "RAW",
    ) -> None:
        row_number = int(range_name.split("A", 1)[1])
        self.rows[row_number - 1] = list(values[0])


class FakeSpreadsheet:
    def __init__(self, schemas: dict[str, tuple[str, ...]]) -> None:
        self.sheets = {
            name: FakeWorksheet(name, headers)
            for name, headers in schemas.items()
        }

    def worksheet(self, name: str) -> FakeWorksheet:
        return self.sheets[name]


def _api_error(status_code: int) -> APIError:
    response = Response()
    response.status_code = status_code
    response._content = (
        f'{{"error":{{"code":{status_code},"message":"Quota exceeded"}}}}'.encode()
    )
    return APIError(response)


def test_credit_is_idempotent_by_payment_and_can_be_consumed() -> None:
    spreadsheet = FakeSpreadsheet(ACCOUNTS_BILLING_SCHEMAS)
    repository = GoogleSheetsStoryCreditRepository(spreadsheet)  # type: ignore[arg-type]

    first = repository.create_credit(
        user_id="user-1",
        package_id="casada_frustrada",
        payment_id="payment-1",
    )
    repeated = repository.create_credit(
        user_id="user-1",
        package_id="casada_frustrada",
        payment_id="payment-1",
    )

    assert repeated.credit_id == first.credit_id
    consumed = repository.consume_credit(credit_id=first.credit_id, run_id="run-1")
    assert consumed.status == "consumed"
    assert consumed.run_id == "run-1"

    with pytest.raises(RuntimeConflictError):
        repository.consume_credit(credit_id=first.credit_id, run_id="run-2")


def test_run_update_uses_optimistic_version() -> None:
    spreadsheet = FakeSpreadsheet(RUNTIME_SCHEMAS)
    repository = GoogleSheetsStoryRunRepository(spreadsheet)  # type: ignore[arg-type]
    credit = RunCredit(
        credit_id="credit-1",
        user_id="user-1",
        package_id="casada_frustrada",
        payment_id="payment-1",
        status="available",
    )
    run = repository.create_run(
        credit=credit,
        script_version="2.0.0",
        first_block_id="supermercado",
        first_beat_id="supermercado_001",
    )
    run.current_beat_id = "supermercado_002"

    updated = repository.update_run(run=run, expected_version=1)
    assert updated.state_version == 2
    assert updated.current_beat_id == "supermercado_002"

    with pytest.raises(RuntimeConflictError):
        repository.update_run(run=run, expected_version=1)


def test_memory_is_not_duplicated() -> None:
    spreadsheet = FakeSpreadsheet(RUNTIME_SCHEMAS)
    repository = GoogleSheetsStoryRunRepository(spreadsheet)  # type: ignore[arg-type]

    repository.append_run_memory(
        run_id="run-1",
        memory_id="encontro_supermercado",
        source_beat_id="supermercado_005",
    )
    repository.append_run_memory(
        run_id="run-1",
        memory_id="encontro_supermercado",
        source_beat_id="supermercado_005",
    )

    rows = spreadsheet.worksheet("RUN_MEMORIES").get_all_records()
    assert len(rows) == 1


def test_recent_interactions_are_limited_and_ordered() -> None:
    spreadsheet = FakeSpreadsheet(RUNTIME_SCHEMAS)
    repository = GoogleSheetsNarrativeInteractionRepository(spreadsheet)  # type: ignore[arg-type]

    for sequence in range(1, 9):
        repository.append_interaction(
            run_id="run-1",
            user_id="user-1",
            package_id="casada_frustrada",
            sequence=sequence,
            role="user",
            content=f"mensagem {sequence}",
            block_id="supermercado",
            beat_id="supermercado_001",
            speaker_id="user",
        )

    recent = repository.list_recent_interactions(run_id="run-1", limit=4)
    assert [int(row["sequence"]) for row in recent] == [5, 6, 7, 8]


def test_sheet_table_reuses_reads_and_updates_cache_after_write() -> None:
    spreadsheet = FakeSpreadsheet({"TEST": ("id", "value")})
    worksheet = spreadsheet.worksheet("TEST")
    table = _SheetTable(spreadsheet, "TEST")  # type: ignore[arg-type]

    table.append({"id": "1", "value": "primeiro"})
    first = table.records()
    repeated = table.records()
    table.replace(2, {"id": "1", "value": "atualizado"})
    updated = table.records()

    assert first == repeated == [{"id": "1", "value": "primeiro"}]
    assert updated == [{"id": "1", "value": "atualizado"}]
    assert worksheet.header_reads == 1
    assert worksheet.record_reads == 1


def test_sheet_table_serves_last_safe_snapshot_during_read_quota(monkeypatch) -> None:
    clock = [0.0]
    monkeypatch.setattr(v2_google_sheets, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        v2_google_sheets,
        "with_transient_retry",
        lambda operation, **_kwargs: operation(),
    )
    spreadsheet = FakeSpreadsheet({"TEST": ("id", "value")})
    worksheet = spreadsheet.worksheet("TEST")
    worksheet.rows.append(["1", "seguro"])
    table = _SheetTable(spreadsheet, "TEST")  # type: ignore[arg-type]

    assert table.records() == [{"id": "1", "value": "seguro"}]
    clock[0] = 30.0
    worksheet.read_error = _api_error(429)

    assert table.records() == [{"id": "1", "value": "seguro"}]


def test_sheet_table_without_snapshot_returns_recoverable_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        v2_google_sheets,
        "with_transient_retry",
        lambda operation, **_kwargs: operation(),
    )
    spreadsheet = FakeSpreadsheet({"TEST": ("id", "value")})
    spreadsheet.worksheet("TEST").read_error = _api_error(429)
    table = _SheetTable(spreadsheet, "TEST")  # type: ignore[arg-type]

    with pytest.raises(GoogleSheetsTemporarilyUnavailable):
        table.records()


def test_runtime_reuses_active_session_for_same_instance() -> None:
    spreadsheet = FakeSpreadsheet(RUNTIME_SCHEMAS)
    repository = GoogleSheetsV2RuntimeRepository(spreadsheet)  # type: ignore[arg-type]

    first = repository.create_session(
        run_id="run-1",
        user_id="user-1",
        package_id="story-1",
        instance_id="flet_user-1",
    )
    repeated = repository.create_session(
        run_id="run-1",
        user_id="user-1",
        package_id="story-1",
        instance_id="flet_user-1",
    )

    assert repeated.session_id == first.session_id
    assert len(spreadsheet.worksheet("SESSIONS").get_all_records()) == 1


def test_editorial_repository_does_not_reload_roteiros_per_balloon() -> None:
    spreadsheet = FakeSpreadsheet(
        {
            "ROTEIROS": (
                "package_id",
                "script_version",
                "line_id",
                "order",
                "instruction",
                "status",
            )
        }
    )
    worksheet = spreadsheet.worksheet("ROTEIROS")
    worksheet.rows.append(
        ["story-1", "1.0", "quadro_001_descricao", 1, "[DESCRIÇÃO] Cena.", "active"]
    )
    repository = GoogleSheetsEditorialRepository(spreadsheet)  # type: ignore[arg-type]

    first = repository.load_active_story_lines("story-1")
    repeated = repository.load_active_story_lines("story-1")

    assert repeated == first
    assert worksheet.record_reads == 1
