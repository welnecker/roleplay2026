from __future__ import annotations

from typing import Any

from flet_client.api_client import FletApiClient, FletApiError


class FakeResponse:
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail

    def json(self):
        return {"detail": self.detail}


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def request(self, *_args: Any, **_kwargs: Any):
        return self.response


def _error(status_code: int) -> FletApiError:
    client = FletApiClient(
        "https://api.example.com",
        session=FakeSession(FakeResponse(status_code, "erro")),  # type: ignore[arg-type]
    )
    client.access_token = "token-preservado"
    try:
        client.catalog()
    except FletApiError as exc:
        assert client.access_token == "token-preservado"
        return exc
    raise AssertionError("Era esperado FletApiError")


def test_runtime_conflict_does_not_look_like_authentication_failure() -> None:
    exc = _error(409)
    assert exc.status_code == 409
    assert exc.is_authentication_error is False


def test_only_401_is_authentication_failure() -> None:
    exc = _error(401)
    assert exc.status_code == 401
    assert exc.is_authentication_error is True
