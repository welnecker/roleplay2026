from __future__ import annotations

from types import SimpleNamespace
from time import monotonic

from persistence import accounts as accounts_module
from persistence import editorial as editorial_module
from persistence import runtime_v2 as runtime_module
from persistence import v2_google_sheets as v2_module
from persistence.sheets_read_optimization import (
    cache_ttl_for,
    install,
    roteiros_cache_ttl,
    users_lookup_cache_ttl,
)


def test_interactions_keeps_short_read_window() -> None:
    assert cache_ttl_for("INTERACTIONS") == 20.0
    assert cache_ttl_for("STORY_RUNS") > cache_ttl_for("INTERACTIONS")
    assert cache_ttl_for("RUN_MEMORIES") > cache_ttl_for("INTERACTIONS")
    assert cache_ttl_for("SESSIONS") > cache_ttl_for("INTERACTIONS")


def test_roteiros_and_users_have_bounded_read_caches() -> None:
    assert roteiros_cache_ttl() >= 10.0
    assert users_lookup_cache_ttl() >= 10.0


def test_policy_sheet_table_extends_cache_by_sheet_without_google_call() -> None:
    install()
    table_class = v2_module._SheetTable

    memories = table_class(None, "RUN_MEMORIES")
    memories._records_cache = (monotonic() + 1.0, [])
    memories.records()
    memory_remaining = memories._records_cache[0] - monotonic()
    assert memory_remaining > 250.0

    interactions = table_class(None, "INTERACTIONS")
    interactions._records_cache = (monotonic() + 1.0, [])
    interactions.records()
    interaction_remaining = interactions._records_cache[0] - monotonic()
    assert 15.0 < interaction_remaining <= 21.0


def test_active_runtime_session_is_reused_without_sheet_lookup() -> None:
    install()
    repository = object.__new__(runtime_module.GoogleSheetsV2RuntimeRepository)
    expected = SimpleNamespace(status="active")
    key = ("run-1", "user-1", "pkg-1", "flet_user-1")
    repository._active_runtime_sessions = {key: expected}

    resolved = repository.create_session(
        run_id="run-1",
        user_id="user-1",
        package_id="pkg-1",
        instance_id="flet_user-1",
    )

    assert resolved is expected


def test_positive_user_lookup_can_be_served_without_sheet_lookup() -> None:
    install()
    repository = object.__new__(accounts_module.GoogleSheetsAccountRepository)
    expected = SimpleNamespace(user_id="user-1", status="active")
    repository._user_lookup_cache = {
        "user-1": (monotonic() + 60.0, expected),
    }

    resolved = repository.get_user(user_id="user-1")

    assert resolved is expected


def test_roteiros_runtime_cache_can_serve_without_sheet_lookup() -> None:
    install()
    repository = object.__new__(editorial_module.GoogleSheetsEditorialRepository)
    repository._runtime_roteiros_cache = (
        monotonic() + 60.0,
        [{"package_id": "pkg-1", "line_id": "linha-1"}],
    )

    rows = repository._records("ROTEIROS")

    assert rows == [{"package_id": "pkg-1", "line_id": "linha-1"}]
    rows[0]["line_id"] = "mutada"
    assert repository._runtime_roteiros_cache[1][0]["line_id"] == "linha-1"
