from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from typing import Any

from persistence.backend_config import POSTGRES_BACKEND, database_url, operational_backend
from persistence.editorial_runtime_v2 import EditorialGoogleSheetsV2RuntimeRepository
from persistence.postgres_database import shared_postgres_database
from persistence.postgres_runtime import PostgresV2RuntimeRepository
from persistence.spreadsheet_config import read_spreadsheet_ids


GOOGLE_SHEETS_CONNECT_TIMEOUT_SECONDS = 20.0


def _connect_runtime_repository(
    *,
    credentials: dict[str, Any],
    spreadsheet_id: str,
) -> EditorialGoogleSheetsV2RuntimeRepository:
    return EditorialGoogleSheetsV2RuntimeRepository.from_service_account(
        credentials=credentials,
        spreadsheet_id=spreadsheet_id,
    )


def build_google_sheets_repository(secrets: Any) -> Any | None:
    """Seleciona o runtime operacional, preservando Sheets como rollback seguro."""

    if operational_backend(secrets) == POSTGRES_BACKEND:
        database = shared_postgres_database(database_url(secrets))
        database.ensure_schema()
        return PostgresV2RuntimeRepository(database)

    credentials = secrets.get("gcp_service_account")
    if not credentials:
        return None

    spreadsheet_ids = read_spreadsheet_ids(secrets)
    result: Queue[tuple[str, object]] = Queue(maxsize=1)

    def connect() -> None:
        try:
            repository = _connect_runtime_repository(
                credentials=dict(credentials),
                spreadsheet_id=spreadsheet_ids.runtime,
            )
        except Exception as exc:
            result.put(("error", exc))
        else:
            result.put(("ok", repository))

    worker = Thread(
        target=connect,
        name="google-sheets-runtime-connect",
        daemon=True,
    )
    worker.start()

    try:
        status, value = result.get(timeout=GOOGLE_SHEETS_CONNECT_TIMEOUT_SECONDS)
    except Empty as exc:
        raise TimeoutError(
            "Google Sheets não respondeu em até "
            f"{GOOGLE_SHEETS_CONNECT_TIMEOUT_SECONDS:.0f} segundos."
        ) from exc

    if status == "error":
        assert isinstance(value, Exception)
        raise value
    assert isinstance(value, EditorialGoogleSheetsV2RuntimeRepository)
    return value
