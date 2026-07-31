from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from persistence.editorial_publisher import (
    _publication_is_complete,
    _replace_package_rows,
)


class FakeWorksheet:
    def __init__(self) -> None:
        self.values = [
            ["package_id", "beat_id", "content"],
            ["other.story", "other_1", "preservar"],
            ["roleplay2026.casada_frustrada", "old_1", "antigo"],
        ]
        self.clear_calls = 0
        self.update_calls = 0

    def row_values(self, row: int) -> list[str]:
        return list(self.values[row - 1])

    def get_all_values(self) -> list[list[str]]:
        return [list(row) for row in self.values]

    def clear(self) -> None:
        self.clear_calls += 1
        self.values = []

    def update(self, *, values: list[list[Any]], range_name: str, value_input_option: str) -> None:
        assert range_name == "A1"
        assert value_input_option == "RAW"
        self.update_calls += 1
        self.values = [list(row) for row in values]


@dataclass
class FakeRepository:
    worksheet: FakeWorksheet
    records_by_sheet: dict[str, list[dict[str, Any]]] | None = None

    def _worksheet(self, name: str) -> FakeWorksheet:
        return self.worksheet

    def _records(self, name: str) -> list[dict[str, Any]]:
        assert self.records_by_sheet is not None
        return self.records_by_sheet.get(name, [])


def test_substitui_todas_as_linhas_do_pacote_em_uma_unica_atualizacao() -> None:
    worksheet = FakeWorksheet()
    repository = FakeRepository(worksheet)
    rows = [
        {
            "package_id": "roleplay2026.casada_frustrada",
            "beat_id": f"beat_{index}",
            "content": f"fala {index}",
        }
        for index in range(117)
    ]

    _replace_package_rows(
        repository,
        sheet_name="BEATS",
        package_id="roleplay2026.casada_frustrada",
        new_rows=rows,
    )

    assert worksheet.clear_calls == 1
    assert worksheet.update_calls == 1
    assert worksheet.values[1] == ["other.story", "other_1", "preservar"]
    assert len(worksheet.values) == 1 + 1 + 117


def test_publicacao_parcial_nao_e_considerada_completa() -> None:
    expected = {
        "STORIES": [{"package_id": "roleplay2026.casada_frustrada"}],
        "CHARACTERS": [{"package_id": "roleplay2026.casada_frustrada"}],
        "BLOCKS": [{"package_id": "roleplay2026.casada_frustrada"}] * 7,
        "BEATS": [{"package_id": "roleplay2026.casada_frustrada"}] * 117,
        "MEMORIES": [{"package_id": "roleplay2026.casada_frustrada"}] * 5,
    }
    records = {
        **expected,
        "BEATS": [{"package_id": "roleplay2026.casada_frustrada"}] * 23,
    }
    repository = FakeRepository(FakeWorksheet(), records)

    assert not _publication_is_complete(
        repository,
        "roleplay2026.casada_frustrada",
        expected,
    )
