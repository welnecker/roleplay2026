from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import gspread
from gspread import Spreadsheet, Worksheet

from persistence.models import (
    ConcurrentSaveUpdateError,
    InteractionRecord,
    SaveRecord,
    SessionRecord,
    new_id,
    utc_now_iso,
)

USERS_SHEET = "USERS"
SAVES_SHEET = "SAVES"
SESSIONS_SHEET = "SESSIONS"
INTERACTIONS_SHEET = "INTERACTIONS"

SHEET_HEADERS: dict[str, tuple[str, ...]] = {
    USERS_SHEET: (
        "user_id",
        "email",
        "display_name",
        "status",
        "created_at",
        "updated_at",
    ),
    SAVES_SHEET: (
        "save_id",
        "user_id",
        "package_id",
        "package_version",
        "state_version",
        "state_json",
        "status",
        "created_at",
        "updated_at",
    ),
    SESSIONS_SHEET: (
        "session_id",
        "save_id",
        "user_id",
        "package_id",
        "instance_id",
        "status",
        "started_at",
        "last_seen_at",
        "ended_at",
    ),
    INTERACTIONS_SHEET: (
        "interaction_id",
        "session_id",
        "save_id",
        "user_id",
        "package_id",
        "role",
        "content",
        "sequence",
        "created_at",
        "metadata_json",
    ),
}


class GoogleSheetsRuntimeRepository:
    """Persistência compartilhada para o runtime narrativo.

    Interações e sessões são append-only. Saves usam state_version para
    detectar atualização concorrente entre múltiplas instâncias.
    """

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.spreadsheet = spreadsheet
        self._worksheets: dict[str, Worksheet] = {}

    @classmethod
    def from_service_account(
        cls,
        *,
        credentials: dict[str, Any],
        spreadsheet_id: str,
    ) -> "GoogleSheetsRuntimeRepository":
        client = gspread.service_account_from_dict(credentials)
        return cls(client.open_by_key(spreadsheet_id))

    def ensure_schema(self) -> None:
        for name, headers in SHEET_HEADERS.items():
            worksheet = self._get_or_create_worksheet(name, rows=1000, cols=len(headers))
            current = tuple(str(value).strip() for value in worksheet.row_values(1))
            if not current:
                worksheet.append_row(list(headers), value_input_option="RAW")
            elif current != headers:
                raise RuntimeError(
                    f"Cabeçalhos incompatíveis na aba {name}: esperado={headers}, atual={current}"
                )

    def upsert_user(self, *, user_id: str, email: str, display_name: str) -> None:
        now = utc_now_iso()
        worksheet = self._worksheet(USERS_SHEET)
        found = self._find_row(worksheet, "user_id", user_id)
        if found is None:
            self._append(
                worksheet,
                {
                    "user_id": user_id,
                    "email": email,
                    "display_name": display_name,
                    "status": "active",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            return
        row_number, row = found
        row.update(
            {
                "email": email,
                "display_name": display_name,
                "status": "active",
                "updated_at": now,
            }
        )
        self._replace_row(worksheet, row_number, row)

    def get_active_save(self, *, user_id: str, package_id: str) -> SaveRecord | None:
        candidates = [
            row
            for row in self._records(SAVES_SHEET)
            if row.get("user_id") == user_id
            and row.get("package_id") == package_id
            and row.get("status") == "active"
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda row: str(row.get("updated_at", "")), reverse=True)
        return self._save_from_row(candidates[0])

    def create_save(
        self,
        *,
        user_id: str,
        package_id: str,
        package_version: str,
        state: dict[str, Any],
    ) -> SaveRecord:
        now = utc_now_iso()
        record = SaveRecord(
            save_id=new_id("save"),
            user_id=user_id,
            package_id=package_id,
            package_version=package_version,
            state_version=1,
            state=dict(state),
            status="active",
            created_at=now,
            updated_at=now,
        )
        self._append(self._worksheet(SAVES_SHEET), self._save_to_row(record))
        return record

    def update_save(
        self,
        *,
        save_id: str,
        expected_version: int,
        state: dict[str, Any],
        status: str = "active",
    ) -> SaveRecord:
        worksheet = self._worksheet(SAVES_SHEET)
        found = self._find_row(worksheet, "save_id", save_id)
        if found is None:
            raise KeyError(f"Save não encontrado: {save_id}")
        row_number, row = found
        current = self._save_from_row(row)
        if current.state_version != expected_version:
            raise ConcurrentSaveUpdateError(
                f"Versão concorrente no save {save_id}: esperada={expected_version}, "
                f"atual={current.state_version}"
            )
        updated = SaveRecord(
            save_id=current.save_id,
            user_id=current.user_id,
            package_id=current.package_id,
            package_version=current.package_version,
            state_version=current.state_version + 1,
            state=dict(state),
            status=status,
            created_at=current.created_at,
            updated_at=utc_now_iso(),
        )
        self._replace_row(worksheet, row_number, self._save_to_row(updated))
        return updated

    def create_session(
        self,
        *,
        save_id: str,
        user_id: str,
        package_id: str,
        instance_id: str,
    ) -> SessionRecord:
        now = utc_now_iso()
        record = SessionRecord(
            session_id=new_id("sess"),
            save_id=save_id,
            user_id=user_id,
            package_id=package_id,
            instance_id=instance_id,
            status="active",
            started_at=now,
            last_seen_at=now,
        )
        self._append(self._worksheet(SESSIONS_SHEET), asdict(record))
        return record

    def append_interaction(
        self,
        *,
        session_id: str,
        save_id: str,
        user_id: str,
        package_id: str,
        role: str,
        content: str,
        sequence: int,
        metadata: dict[str, Any] | None = None,
    ) -> InteractionRecord:
        record = InteractionRecord(
            interaction_id=new_id("int"),
            session_id=session_id,
            save_id=save_id,
            user_id=user_id,
            package_id=package_id,
            role=role,
            content=content,
            sequence=sequence,
            created_at=utc_now_iso(),
            metadata=dict(metadata or {}),
        )
        row = asdict(record)
        row["metadata_json"] = self._json(record.metadata)
        row.pop("metadata")
        self._append(self._worksheet(INTERACTIONS_SHEET), row)
        return record

    def list_interactions(self, *, save_id: str, limit: int = 50) -> list[InteractionRecord]:
        rows = [row for row in self._records(INTERACTIONS_SHEET) if row.get("save_id") == save_id]
        rows.sort(key=lambda row: int(row.get("sequence", 0)))
        selected = rows[-max(1, limit) :]
        return [
            InteractionRecord(
                interaction_id=str(row["interaction_id"]),
                session_id=str(row["session_id"]),
                save_id=str(row["save_id"]),
                user_id=str(row["user_id"]),
                package_id=str(row["package_id"]),
                role=str(row["role"]),
                content=str(row["content"]),
                sequence=int(row["sequence"]),
                created_at=str(row["created_at"]),
                metadata=self._parse_json(row.get("metadata_json")),
            )
            for row in selected
        ]

    def _worksheet(self, name: str) -> Worksheet:
        if name not in self._worksheets:
            self._worksheets[name] = self.spreadsheet.worksheet(name)
        return self._worksheets[name]

    def _get_or_create_worksheet(self, name: str, *, rows: int, cols: int) -> Worksheet:
        try:
            return self._worksheet(name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(title=name, rows=rows, cols=cols)
            self._worksheets[name] = worksheet
            return worksheet

    def _records(self, sheet_name: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self._worksheet(sheet_name).get_all_records(default_blank="")]

    def _find_row(
        self,
        worksheet: Worksheet,
        key: str,
        value: str,
    ) -> tuple[int, dict[str, Any]] | None:
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        if key not in headers:
            raise RuntimeError(f"Coluna ausente em {worksheet.title}: {key}")
        for row_number, row in enumerate(worksheet.get_all_records(default_blank=""), start=2):
            if str(row.get(key, "")).strip() == value:
                return row_number, dict(row)
        return None

    def _append(self, worksheet: Worksheet, data: dict[str, Any]) -> None:
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        worksheet.append_row([data.get(header, "") for header in headers], value_input_option="RAW")

    def _replace_row(self, worksheet: Worksheet, row_number: int, data: dict[str, Any]) -> None:
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        worksheet.update(
            range_name=f"A{row_number}",
            values=[[data.get(header, "") for header in headers]],
            value_input_option="RAW",
        )

    @classmethod
    def _save_to_row(cls, record: SaveRecord) -> dict[str, Any]:
        row = asdict(record)
        row["state_json"] = cls._json(record.state)
        row.pop("state")
        return row

    @classmethod
    def _save_from_row(cls, row: dict[str, Any]) -> SaveRecord:
        return SaveRecord(
            save_id=str(row["save_id"]),
            user_id=str(row["user_id"]),
            package_id=str(row["package_id"]),
            package_version=str(row["package_version"]),
            state_version=int(row["state_version"]),
            state=cls._parse_json(row.get("state_json")),
            status=str(row["status"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _json(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _parse_json(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        parsed = json.loads(str(value))
        return dict(parsed) if isinstance(parsed, dict) else {}
