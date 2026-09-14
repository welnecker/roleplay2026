from __future__ import annotations

from typing import Any

from persistence.spreadsheet_config import read_spreadsheet_ids
from persistence.backend_config import POSTGRES_BACKEND, operational_backend
from persistence.v2_google_sheets import GoogleSheetsNarrativeRepositories


def build_v2_narrative_repositories(
    secrets: Any,
) -> Any:
    """Cria os repositórios operacionais da arquitetura narrativa v2.

    A planilha editorial não é aberta aqui porque o runtime publicado deve ler
    os roteiros versionados no repositório, e não consultar o Sheets a cada turno.
    """

    if operational_backend(secrets) == POSTGRES_BACKEND:
        from persistence.postgres_database import shared_postgres_database
        from persistence.postgres_narrative import PostgresNarrativeRepositories

        return PostgresNarrativeRepositories(shared_postgres_database(secrets))

    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("[gcp_service_account] não está configurado.")

    spreadsheet_ids = read_spreadsheet_ids(secrets)
    return GoogleSheetsNarrativeRepositories.from_service_account(
        credentials=dict(credentials),
        accounts_billing_spreadsheet_id=spreadsheet_ids.accounts_billing,
        runtime_spreadsheet_id=spreadsheet_ids.runtime,
    )
