from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Any

from psycopg_pool import ConnectionPool

from persistence.backend_config import database_url


MIGRATIONS_ROOT = Path(__file__).resolve().parent.parent / "migrations"
_SCHEMA_LOCK = Lock()


class PostgresDatabase:
    """Pool compartilhado e migrations idempotentes do armazenamento operacional."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 8) -> None:
        if not str(dsn or "").strip():
            raise ValueError("A URL do PostgreSQL não pode ficar vazia.")
        self.pool = ConnectionPool(
            conninfo=dsn,
            min_size=max(1, int(min_size)),
            max_size=max(max(1, int(min_size)), int(max_size)),
            timeout=10.0,
            kwargs={"autocommit": False},
            open=True,
        )

    @classmethod
    def from_secrets(cls, secrets: Any) -> "PostgresDatabase":
        return cls(
            database_url(secrets),
            min_size=int(os.getenv("POSTGRES_POOL_MIN_SIZE", "1")),
            max_size=int(os.getenv("POSTGRES_POOL_MAX_SIZE", "8")),
        )

    def ensure_schema(self) -> None:
        with _SCHEMA_LOCK:
            with self.pool.connection() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version text PRIMARY KEY,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                for migration in sorted(MIGRATIONS_ROOT.glob("*.sql")):
                    version = migration.stem
                    exists = connection.execute(
                        "SELECT 1 FROM schema_migrations WHERE version = %s",
                        (version,),
                    ).fetchone()
                    if exists is not None:
                        continue
                    sql = migration.read_text(encoding="utf-8")
                    with connection.transaction():
                        connection.execute(sql, prepare=False)
                        connection.execute(
                            "INSERT INTO schema_migrations(version) VALUES (%s)",
                            (version,),
                        )
                connection.commit()

    def close(self) -> None:
        self.pool.close()


_DATABASES: dict[str, PostgresDatabase] = {}
_DATABASES_LOCK = Lock()


def shared_postgres_database(secrets: Any) -> PostgresDatabase:
    dsn = database_url(secrets)
    with _DATABASES_LOCK:
        database = _DATABASES.get(dsn)
        if database is None:
            database = PostgresDatabase.from_secrets(secrets)
            database.ensure_schema()
            _DATABASES[dsn] = database
        return database
