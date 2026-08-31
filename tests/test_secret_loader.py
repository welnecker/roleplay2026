from __future__ import annotations

import json

import pytest

from services.secret_loader import load_application_secrets


def test_loads_google_service_account_from_json_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    service_account = {
        "type": "service_account",
        "project_id": "roleplay-test",
        "private_key": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----\n",
        "client_email": "service@example.test",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", json.dumps(service_account))
    monkeypatch.setenv("GOOGLE_SHEETS_SPREADSHEET_ID", "sheet-123")
    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "token-123")

    secrets = load_application_secrets()

    assert secrets["GOOGLE_SHEETS_SPREADSHEET_ID"] == "sheet-123"
    assert secrets["MERCADO_PAGO_ACCESS_TOKEN"] == "token-123"
    assert secrets["gcp_service_account"]["client_email"] == "service@example.test"
    assert "\n" in secrets["gcp_service_account"]["private_key"]


def test_loads_openrouter_configuration_from_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "provider/story-model")
    monkeypatch.setenv("OPENROUTER_INTENT_MODEL", "provider/intent-model")

    secrets = load_application_secrets()

    assert secrets["OPENROUTER_API_KEY"] == "openrouter-key"
    assert secrets["OPENROUTER_MODEL"] == "provider/story-model"
    assert secrets["OPENROUTER_INTENT_MODEL"] == "provider/intent-model"


def test_loads_google_service_account_from_individual_environment(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GCP_SERVICE_ACCOUNT_JSON", raising=False)
    monkeypatch.setenv("GCP_PROJECT_ID", "roleplay-test")
    monkeypatch.setenv("GCP_CLIENT_EMAIL", "service@example.test")
    monkeypatch.setenv("GCP_PRIVATE_KEY", "line1\\nline2")

    secrets = load_application_secrets()

    account = secrets["gcp_service_account"]
    assert account["type"] == "service_account"
    assert account["project_id"] == "roleplay-test"
    assert account["private_key"] == "line1\nline2"


def test_rejects_invalid_service_account_json(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GCP_SERVICE_ACCOUNT_JSON", "not-json")

    with pytest.raises(RuntimeError, match="JSON inválido"):
        load_application_secrets()
