from __future__ import annotations

from typing import Any

import pytest

from narrative_v2.models import RunCredit
from narrative_v2.repository import RuntimeConflictError
from persistence.v2_google_sheets import (
    GoogleSheetsNarrativeInteractionRepository,
    GoogleSheetsStoryCreditRepository,
    GoogleSheetsStoryRunRepository,
)
from persistence.v2_schemas import ACCOUNTS_BILLING_SCHEMAS, RUNTIME_SCHEMAS


class FakeWorksheet:
    def __init__(self, title: str, headers: tuple[str, ...]) -> None:
        self.title = title
        self.rows: list[list[Any]] = [list(headers)]

    def row_values(self, row_number: int) -> list[Any]:
        return list(self.rows[row_number - 1]) if row_number <= len(self.rows) else []

    def get_all_records(self, default_blank: str = "") -> list[dict[str, Any]]:
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
