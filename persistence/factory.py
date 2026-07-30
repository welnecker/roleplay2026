from __future__ import annotations

from typing import Any

from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository
from persistence.spreadsheet_config import read_spreadsheet_ids


def build_google_sheets_repository(
    secrets: Any,
) -> GoogleSheetsV2RuntimeRepository | None:
    """Cria a conexão exclusiva com ROLEPLAY_RUNTIME.

    As abas são preparadas pelo processo explícito de instalação/migração. O
    caminho normal do usuário não valida schemas nem consulta a planilha antiga.
    """

    credentials = secrets.get("gcp_service_account")
    if not credentials:
        return None
    spreadsheet_ids = read_spreadsheet_ids(secrets)
    return GoogleSheetsV2RuntimeRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=spreadsheet_ids.runtime,
    )
