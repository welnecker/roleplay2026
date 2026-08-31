from __future__ import annotations

from types import SimpleNamespace

import persistence.accounts as accounts
from platform_core.auth import demo_auth_allowed


class _Repository:
    def __init__(self, spreadsheet: object) -> None:
        self.spreadsheet = spreadsheet
        self.schema_checked = False

    def ensure_schema(self) -> None:
        self.schema_checked = True


def test_account_repository_uses_accounts_billing_sheet_directly(monkeypatch) -> None:
    opened: list[str] = []
    spreadsheet = object()
    client = SimpleNamespace(
        open_by_key=lambda key: opened.append(key) or spreadsheet
    )
    monkeypatch.setattr(
        accounts.gspread,
        "service_account_from_dict",
        lambda credentials: client,
    )
    monkeypatch.setattr(accounts, "GoogleSheetsAccountRepository", _Repository)

    repository = accounts.build_account_repository(
        {
            "gcp_service_account": {"client_email": "service@example.com"},
            "ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID": "accounts-billing",
        }
    )

    assert opened == ["accounts-billing"]
    assert repository.spreadsheet is spreadsheet
    assert repository.schema_checked is True


def test_demo_login_is_disabled_when_real_google_credentials_exist() -> None:
    assert demo_auth_allowed({}) is True
    assert demo_auth_allowed({"gcp_service_account": {"client_email": "x"}}) is False
