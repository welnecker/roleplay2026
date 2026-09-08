from __future__ import annotations

import pytest
from gspread.exceptions import APIError
from requests import Response

from persistence import google_sheets_retry as retry


def _api_error(status: int) -> APIError:
    response = Response()
    response.status_code = status
    response._content = (
        f'{{"error":{{"code":{status},"message":"temporary"}}}}'.encode()
    )
    return APIError(response)


def test_retries_503_until_google_recovers(monkeypatch) -> None:
    delays: list[float] = []
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _api_error(503)
        return "connected"

    monkeypatch.setattr(retry.time, "sleep", delays.append)

    assert retry.with_transient_retry(operation) == "connected"
    assert calls == 3
    assert delays == [1.0, 2.0]


def test_does_not_retry_permanent_google_error(monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr(retry.time, "sleep", slept.append)

    with pytest.raises(APIError):
        retry.with_transient_retry(lambda: (_ for _ in ()).throw(_api_error(403)))

    assert slept == []


def test_raises_after_transient_retry_limit(monkeypatch) -> None:
    monkeypatch.setattr(retry.time, "sleep", lambda _delay: None)

    with pytest.raises(APIError):
        retry.with_transient_retry(
            lambda: (_ for _ in ()).throw(_api_error(503)),
            attempts=3,
        )
