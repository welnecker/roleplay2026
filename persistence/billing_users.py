from __future__ import annotations

from typing import Any

from gspread import Spreadsheet

from persistence.models import utc_now_iso


class GoogleSheetsBillingUserRepository:
    """Usuários espelhados em ROLEPLAY_ACCOUNTS_BILLING/USERS."""

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.worksheet = spreadsheet.worksheet("USERS")
        self._headers: list[str] | None = None

    def _get_headers(self) -> list[str]:
        if self._headers is None:
            self._headers = [str(value).strip() for value in self.worksheet.row_values(1)]
        return self._headers

    def upsert_user(
        self,
        *,
        user_id: str,
        email: str,
        display_name: str,
        status: str = "active",
    ) -> None:
        clean_user_id = user_id.strip()
        if not clean_user_id:
            raise ValueError("user_id é obrigatório.")

        headers = self._get_headers()
        rows = self.worksheet.get_all_records(default_blank="")
        now = utc_now_iso()
        data: dict[str, Any] = {
            "user_id": clean_user_id,
            "email": email.strip().lower(),
            "display_name": display_name.strip(),
            "status": status.strip() or "active",
            "created_at": now,
            "updated_at": now,
        }

        for row_number, row in enumerate(rows, start=2):
            if str(row.get("user_id", "")).strip() != clean_user_id:
                continue
            data["created_at"] = str(row.get("created_at", "") or now)
            self.worksheet.update(
                range_name=f"A{row_number}",
                values=[[data.get(header, "") for header in headers]],
                value_input_option="RAW",
            )
            return

        self.worksheet.append_row(
            [data.get(header, "") for header in headers],
            value_input_option="RAW",
        )
