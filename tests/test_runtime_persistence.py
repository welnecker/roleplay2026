from __future__ import annotations

from typing import Any

import pytest

from persistence.google_sheets import GoogleSheetsRuntimeRepository, SHEET_HEADERS
from persistence.models import ConcurrentSaveUpdateError
from roleplay.models import StoryState
from services.runtime_persistence import restore_story_state, serialize_story_state


class FakeWorksheet:
    def __init__(self, title: str) -> None:
        self.title = title
        self.rows: list[list[Any]] = []

    def row_values(self, row: int) -> list[Any]:
        return list(self.rows[row - 1]) if len(self.rows) >= row else []

    def append_row(self, values: list[Any], value_input_option: str = "RAW") -> None:
        self.rows.append(list(values))

    def get_all_records(self, default_blank: str = "") -> list[dict[str, Any]]:
        if not self.rows:
            return []
        headers = self.rows[0]
        return [
            {
                str(header): row[index] if index < len(row) else default_blank
                for index, header in enumerate(headers)
            }
            for row in self.rows[1:]
        ]

    def update(
        self,
        *,
        range_name: str,
        values: list[list[Any]],
        value_input_option: str = "RAW",
    ) -> None:
        row_number = int(range_name[1:])
        self.rows[row_number - 1] = list(values[0])


class FakeSpreadsheet:
    def __init__(self) -> None:
        self.sheets: dict[str, FakeWorksheet] = {}

    def worksheet(self, name: str) -> FakeWorksheet:
        if name not in self.sheets:
            raise LookupError(name)
        return self.sheets[name]

    def add_worksheet(self, *, title: str, rows: int, cols: int) -> FakeWorksheet:
        worksheet = FakeWorksheet(title)
        self.sheets[title] = worksheet
        return worksheet


def make_repository() -> GoogleSheetsRuntimeRepository:
    spreadsheet = FakeSpreadsheet()
    repository = GoogleSheetsRuntimeRepository(spreadsheet)  # type: ignore[arg-type]
    for name, headers in SHEET_HEADERS.items():
        worksheet = spreadsheet.add_worksheet(title=name, rows=100, cols=len(headers))
        worksheet.append_row(list(headers))
        repository._worksheets[name] = worksheet  # test double wiring
    return repository


def test_story_state_roundtrip() -> None:
    state = StoryState(step_index=2, consumed_orders=[1, 2, 3], finished=False)
    restored = restore_story_state(serialize_story_state(state))
    assert restored.step_index == 2
    assert restored.consumed_orders == [1, 2, 3]
    assert restored.finished is False


def test_save_update_detects_concurrent_instance() -> None:
    repository = make_repository()
    save = repository.create_save(
        user_id="user_1",
        package_id="story.one",
        package_version="1.0.0",
        state={"step_index": 0},
    )

    updated = repository.update_save(
        save_id=save.save_id,
        expected_version=1,
        state={"step_index": 1},
    )
    assert updated.state_version == 2

    with pytest.raises(ConcurrentSaveUpdateError):
        repository.update_save(
            save_id=save.save_id,
            expected_version=1,
            state={"step_index": 99},
        )


def test_interactions_are_isolated_by_save() -> None:
    repository = make_repository()
    for save_id, content in (("save_a", "A"), ("save_b", "B")):
        repository.append_interaction(
            session_id=f"session_{save_id}",
            save_id=save_id,
            user_id="user_1",
            package_id="story.one",
            role="user",
            content=content,
            sequence=1,
        )

    assert [item.content for item in repository.list_interactions(save_id="save_a")] == ["A"]
    assert [item.content for item in repository.list_interactions(save_id="save_b")] == ["B"]
