from __future__ import annotations

from pathlib import Path

import pytest

from persistence.backend_config import (
    POSTGRES_BACKEND,
    SHEETS_BACKEND,
    database_url,
    operational_backend,
)


def test_sheets_remains_safe_default(monkeypatch) -> None:
    monkeypatch.delenv("PERSISTENCE_BACKEND", raising=False)
    assert operational_backend({}) == SHEETS_BACKEND


def test_postgres_requires_database_url(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        database_url({"PERSISTENCE_BACKEND": POSTGRES_BACKEND})


def test_postgres_schema_protects_core_concurrency_invariants() -> None:
    source = (
        Path(__file__).resolve().parent.parent
        / "migrations"
        / "001_postgres_operational.sql"
    ).read_text(encoding="utf-8")

    assert "one_active_run_per_user_package" in source
    assert "interaction_sequence_role_unique" in source
    assert "story_credit_payment_unique" in source
    assert "webhook_provider_event_unique" in source
    assert "ROTEIROS" in source
