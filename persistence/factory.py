from __future__ import annotations

from typing import Any

from persistence.google_sheets import GoogleSheetsRuntimeRepository


def build_google_sheets_repository(
    secrets: Any,
) -> GoogleSheetsRuntimeRepository | None:
    """Cria a conexão com a persistência sem validar schemas em cada acesso.

    A criação e a validação das abas pertencem ao processo explícito de
    instalação/migração. Executar ``ensure_schema`` durante a abertura do app
    multiplica leituras no Google Sheets antes mesmo do login.
    """

    spreadsheet_id = str(secrets.get("GOOGLE_SHEETS_SPREADSHEET_ID", "") or "").strip()
    credentials = secrets.get("gcp_service_account")
    if not spreadsheet_id or not credentials:
        return None

    return GoogleSheetsRuntimeRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=spreadsheet_id,
    )
