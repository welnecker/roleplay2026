from __future__ import annotations

import time

import pytest

from persistence import factory


class _Secrets(dict):
    pass


def _secrets() -> _Secrets:
    return _Secrets(
        gcp_service_account={"project_id": "test"},
        ROLEPLAY_RUNTIME_SPREADSHEET_ID="runtime-sheet",
        ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID="accounts-sheet",
        ROLEPLAY_EDITORIAL_SPREADSHEET_ID="editorial-sheet",
    )


def test_sem_credenciais_retorna_none() -> None:
    assert factory.build_google_sheets_repository({}) is None


def test_conexao_lenta_expira_sem_bloquear_indefinidamente(monkeypatch) -> None:
    monkeypatch.setattr(factory, "GOOGLE_SHEETS_CONNECT_TIMEOUT_SECONDS", 0.02)

    def slow_connect(**_kwargs):
        time.sleep(0.2)
        raise AssertionError("resultado tardio não deve bloquear a interface")

    monkeypatch.setattr(factory, "_connect_runtime_repository", slow_connect)

    started = time.monotonic()
    with pytest.raises(TimeoutError, match="Google Sheets não respondeu"):
        factory.build_google_sheets_repository(_secrets())
    elapsed = time.monotonic() - started

    assert elapsed < 0.15


def test_conexao_lenta_dentro_do_limite_e_aceita(monkeypatch) -> None:
    monkeypatch.setattr(factory, "GOOGLE_SHEETS_CONNECT_TIMEOUT_SECONDS", 0.2)
    repository = object.__new__(factory.EditorialGoogleSheetsV2RuntimeRepository)

    def slow_connect(**_kwargs):
        time.sleep(0.05)
        return repository

    monkeypatch.setattr(factory, "_connect_runtime_repository", slow_connect)

    assert factory.build_google_sheets_repository(_secrets()) is repository


def test_erro_da_conexao_e_repassado(monkeypatch) -> None:
    monkeypatch.setattr(factory, "GOOGLE_SHEETS_CONNECT_TIMEOUT_SECONDS", 0.2)

    def fail_connect(**_kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(factory, "_connect_runtime_repository", fail_connect)

    with pytest.raises(RuntimeError, match="falha simulada"):
        factory.build_google_sheets_repository(_secrets())
