from __future__ import annotations

from typing import Any

from persistence.spreadsheet_config import read_spreadsheet_ids
from persistence.v2_sheet_manager import (
    GoogleSheetsV2SchemaManager,
    SchemaInitializationResult,
)


def initialize_v2_sheet_schemas(
    secrets: Any,
) -> tuple[SchemaInitializationResult, ...]:
    """Abre as três planilhas configuradas e garante seus schemas.

    Esta função deve ser chamada uma única vez na configuração inicial ou em
    uma migração explícita. Ela não deve rodar a cada mensagem do usuário.
    """

    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("[gcp_service_account] não está configurado.")

    manager = GoogleSheetsV2SchemaManager.from_service_account(
        credentials=dict(credentials),
        spreadsheet_ids=read_spreadsheet_ids(secrets),
    )
    return manager.ensure_all()
