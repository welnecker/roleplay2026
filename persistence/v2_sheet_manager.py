from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import gspread
from gspread import Spreadsheet, Worksheet

from persistence.spreadsheet_config import SpreadsheetIds
from persistence.v2_schemas import (
    ACCOUNTS_BILLING_SCHEMAS,
    EDITORIAL_SCHEMAS,
    RUNTIME_SCHEMAS,
)


@dataclass(frozen=True, slots=True)
class SchemaInitializationResult:
    spreadsheet_name: str
    created_sheets: tuple[str, ...]
    existing_sheets: tuple[str, ...]


class GoogleSheetsV2SchemaManager:
    """Cria e valida as abas coletivas da arquitetura narrativa v2.

    O processo é idempotente: abas existentes com cabeçalhos corretos são
    preservadas. Cabeçalhos divergentes geram erro e nunca são sobrescritos.
    """

    def __init__(
        self,
        *,
        accounts_billing: Spreadsheet,
        runtime: Spreadsheet,
        editorial: Spreadsheet,
    ) -> None:
        self.accounts_billing = accounts_billing
        self.runtime = runtime
        self.editorial = editorial

    @classmethod
    def from_service_account(
        cls,
        *,
        credentials: dict[str, Any],
        spreadsheet_ids: SpreadsheetIds,
    ) -> "GoogleSheetsV2SchemaManager":
        client = gspread.service_account_from_dict(credentials)
        return cls(
            accounts_billing=client.open_by_key(spreadsheet_ids.accounts_billing),
            runtime=client.open_by_key(spreadsheet_ids.runtime),
            editorial=client.open_by_key(spreadsheet_ids.editorial),
        )

    def ensure_all(self) -> tuple[SchemaInitializationResult, ...]:
        return (
            self._ensure_spreadsheet(
                self.accounts_billing,
                "ROLEPLAY_ACCOUNTS_BILLING",
                ACCOUNTS_BILLING_SCHEMAS,
            ),
            self._ensure_spreadsheet(
                self.runtime,
                "ROLEPLAY_RUNTIME",
                RUNTIME_SCHEMAS,
            ),
            self._ensure_spreadsheet(
                self.editorial,
                "ROLEPLAY_EDITORIAL",
                EDITORIAL_SCHEMAS,
            ),
        )

    @staticmethod
    def _ensure_spreadsheet(
        spreadsheet: Spreadsheet,
        spreadsheet_name: str,
        schemas: Mapping[str, tuple[str, ...]],
    ) -> SchemaInitializationResult:
        created: list[str] = []
        existing: list[str] = []

        for sheet_name, headers in schemas.items():
            worksheet, was_created = GoogleSheetsV2SchemaManager._get_or_create(
                spreadsheet,
                sheet_name,
                len(headers),
            )
            current = tuple(str(value).strip() for value in worksheet.row_values(1))
            if not current:
                worksheet.append_row(list(headers), value_input_option="RAW")
            elif current != headers:
                # Migração aditiva segura: somente novas colunas ao final. Dados
                # existentes preservam suas posições; schemas reordenados falham.
                if headers[: len(current)] != current:
                    raise RuntimeError(
                        f"Cabeçalhos incompatíveis em {spreadsheet_name}/{sheet_name}: "
                        f"esperado={headers}, atual={current}"
                    )
                worksheet.update(
                    range_name="A1",
                    values=[list(headers)],
                    value_input_option="RAW",
                )

            (created if was_created else existing).append(sheet_name)

        return SchemaInitializationResult(
            spreadsheet_name=spreadsheet_name,
            created_sheets=tuple(created),
            existing_sheets=tuple(existing),
        )

    @staticmethod
    def _get_or_create(
        spreadsheet: Spreadsheet,
        sheet_name: str,
        column_count: int,
    ) -> tuple[Worksheet, bool]:
        try:
            return spreadsheet.worksheet(sheet_name), False
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(
                title=sheet_name,
                rows=1000,
                cols=max(column_count, 1),
            )
            return worksheet, True
