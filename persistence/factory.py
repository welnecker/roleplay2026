from __future__ import annotations

from typing import Any

from persistence.google_sheets import GoogleSheetsRuntimeRepository


def build_google_sheets_repository(
    secrets: Any,
) -> GoogleSheetsRuntimeRepository | None:
    """Cria a persistência somente quando todos os secrets existem.

    Secrets esperados:
    - GOOGLE_SHEETS_SPREADSHEET_ID
    - [gcp_service_account]
    """

    spreadsheet_id = str(secrets.get("GOOGLE_SHEETS_SPREADSHEET_ID", "") or "").strip()
    credentials = secrets.get("gcp_service_account")
    if not spreadsheet_id or not credentials:
        return None

    repository = GoogleSheetsRuntimeRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=spreadsheet_id,
    )
    repository.ensure_schema()
    return repository
