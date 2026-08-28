from __future__ import annotations

from typing import Any

import requests

from flet_client.api_client import FletApiClient, FletApiError
from platform_core.models import AccessStatus


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def catalog_payload() -> dict[str, Any]:
    return {
        "items": [
            {
                "package_id": "roleplay2026.camilly",
                "title": "Camilly",
                "subtitle": "Dê uma carona.",
                "description": "Descrição",
                "genres": ["Encontro 18+"],
                "access_status": "owned",
                "price_label": "R$ 1,00",
                "chapter_label": "História completa",
                "cover_url": "https://api.example.com/api/v1/catalog/roleplay2026.camilly/cover",
                "is_tasting": False,
                "profile_name": "Camilly",
                "profile_identity": "Identidade",
                "profile_personality": "Personalidade",
                "profile_intention": "Intenção",
                "replay_requires_purchase": True,
            }
        ]
    }


def test_cliente_flet_autentica_e_envia_bearer_ao_catalogo() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "access_token": "token-opaco",
                    "user": {
                        "user_id": "user-1",
                        "email": "pessoa@example.com",
                        "display_name": "Pessoa",
                    },
                },
            ),
            FakeResponse(200, catalog_payload()),
        ]
    )
    client = FletApiClient("https://api.example.com/", session=session)  # type: ignore[arg-type]

    user = client.login(email="pessoa@example.com", password="senha-segura")
    cards = client.catalog()

    assert user.display_name == "Pessoa"
    assert cards[0].access_status == AccessStatus.OWNED
    assert cards[0].cover_url.startswith("https://api.example.com/")
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer token-opaco"


def test_cliente_flet_exibe_detalhe_de_erro_da_api() -> None:
    session = FakeSession([FakeResponse(401, {"detail": "E-mail ou senha inválidos."})])
    client = FletApiClient("https://api.example.com", session=session)  # type: ignore[arg-type]

    try:
        client.login(email="pessoa@example.com", password="errada")
    except FletApiError as exc:
        assert str(exc) == "E-mail ou senha inválidos."
    else:
        raise AssertionError("Era esperado FletApiError")


def test_cliente_flet_trata_indisponibilidade_da_api() -> None:
    class OfflineSession:
        def request(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
            raise requests.ConnectionError("offline")

    client = FletApiClient("https://api.example.com", session=OfflineSession())  # type: ignore[arg-type]

    try:
        client.catalog()
    except FletApiError as exc:
        assert "conectar" in str(exc)
    else:
        raise AssertionError("Era esperado FletApiError")
