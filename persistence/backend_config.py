from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


SHEETS_BACKEND = "sheets"
POSTGRES_BACKEND = "postgres"


def operational_backend(secrets: Mapping[str, Any]) -> str:
    value = str(
        secrets.get("PERSISTENCE_BACKEND")
        or os.getenv("PERSISTENCE_BACKEND", SHEETS_BACKEND)
    ).strip().casefold()
    if value not in {SHEETS_BACKEND, POSTGRES_BACKEND}:
        raise ValueError(
            "PERSISTENCE_BACKEND deve ser 'sheets' ou 'postgres'."
        )
    return value


def database_url(secrets: Mapping[str, Any]) -> str:
    value = str(
        secrets.get("DATABASE_URL")
        or os.getenv("DATABASE_URL", "")
    ).strip()
    if operational_backend(secrets) == POSTGRES_BACKEND and not value:
        raise ValueError(
            "DATABASE_URL é obrigatória quando PERSISTENCE_BACKEND=postgres."
        )
    return value
