from __future__ import annotations

import logging

from persistence import sheets_audit


def _audit_messages(caplog) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "roleplay2026.sheets_audit"
    ]


def test_sheets_audit_is_disabled_by_default(monkeypatch, caplog) -> None:
    monkeypatch.delenv("SHEETS_AUDIT_ENABLED", raising=False)
    caplog.set_level(logging.WARNING, logger="roleplay2026.sheets_audit")

    sheets_audit.emit(
        sheet="ROTEIROS",
        operation="records",
        cache="HIT",
        rows=10,
        logical_request=True,
    )

    assert _audit_messages(caplog) == []


def test_sheets_audit_logs_request_context_without_payload(monkeypatch, caplog) -> None:
    monkeypatch.setenv("SHEETS_AUDIT_ENABLED", "true")
    caplog.set_level(logging.WARNING, logger="roleplay2026.sheets_audit")

    tokens = sheets_audit.begin_request("post", "/api/v1/runs/advance")
    try:
        sheets_audit.emit(
            sheet="ROTEIROS",
            operation="records",
            cache="HIT",
            rows=428,
            logical_request=True,
        )
    finally:
        sheets_audit.end_request(tokens)

    messages = _audit_messages(caplog)
    assert len(messages) == 1
    message = messages[0]
    assert "route=POST /api/v1/runs/advance" in message
    assert "sheet=ROTEIROS" in message
    assert "op=records" in message
    assert "cache=HIT" in message
    assert "rows=428" in message
    assert "google_read=0" in message


def test_sheets_audit_counts_real_google_calls_and_quota(monkeypatch, caplog) -> None:
    monkeypatch.setenv("SHEETS_AUDIT_ENABLED", "1")
    caplog.set_level(logging.WARNING, logger="roleplay2026.sheets_audit")

    sheets_audit.emit(
        sheet="STORY_RUNS",
        operation="google.get",
        google_read=1,
        status="429",
    )
    sheets_audit.emit(
        sheet="INTERACTIONS",
        operation="google.append_rows",
        google_write=1,
    )

    messages = _audit_messages(caplog)
    assert any(
        "sheet=STORY_RUNS" in message
        and "google_read=1" in message
        and "status=429" in message
        for message in messages
    )
    assert any(
        "sheet=INTERACTIONS" in message
        and "google_write=1" in message
        for message in messages
    )
