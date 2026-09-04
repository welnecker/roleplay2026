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


def test_cliente_web_publica_capa_recebida_pelo_loopback() -> None:
    payload = catalog_payload()
    payload["items"][0]["cover_url"] = (
        "http://127.0.0.1:10000/api/v1/catalog/roleplay2026.camilly/cover"
    )
    session = FakeSession([FakeResponse(200, payload)])
    client = FletApiClient(
        "http://127.0.0.1:10000",
        public_base_url="https://entrecenas-roleplay.com.br",
        session=session,  # type: ignore[arg-type]
    )

    cards = client.catalog()

    assert cards[0].cover_url == (
        "https://entrecenas-roleplay.com.br/api/v1/catalog/roleplay2026.camilly/cover"
    )


def test_cliente_flet_cadastra_e_guarda_o_token() -> None:
    session = FakeSession(
        [
            FakeResponse(
                201,
                {
                    "access_token": "token-cadastro",
                    "user": {
                        "user_id": "user-new",
                        "email": "nova@example.com",
                        "display_name": "Pessoa Nova",
                    },
                },
            )
        ]
    )
    client = FletApiClient("https://api.example.com", session=session)  # type: ignore[arg-type]

    user = client.register(
        display_name="Pessoa Nova",
        email="nova@example.com",
        password="senha-segura",
    )

    assert user.user_id == "user-new"
    assert client.access_token == "token-cadastro"
    assert session.calls[0][1].endswith("/api/v1/auth/register")
    assert session.calls[0][2]["json"] == {
        "display_name": "Pessoa Nova",
        "email": "nova@example.com",
        "password": "senha-segura",
    }


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


def test_cliente_flet_cria_e_confere_pagamento_pix() -> None:
    payload = {
        "package_id": "roleplay2026.camilly",
        "payment_order_id": "pay-1",
        "status": "pending",
        "approved": False,
        "qr_code": "pix-copia-cola",
        "qr_code_base64": "cXI=",
        "ticket_url": "https://example.com/pix",
        "master_test_available": True,
    }
    session = FakeSession([FakeResponse(200, payload), FakeResponse(200, {**payload, "approved": True})])
    client = FletApiClient("https://api.example.com", session=session)  # type: ignore[arg-type]
    client.access_token = "token"

    created = client.create_pix("roleplay2026.camilly")
    approved = client.refresh_payment(created.payment_order_id)

    assert created.qr_code == "pix-copia-cola"
    assert created.master_test_available is True
    assert approved.approved is True
    assert session.calls[0][2]["json"] == {"package_id": "roleplay2026.camilly"}
    assert session.calls[1][2]["json"] == {"payment_order_id": "pay-1"}


def test_cliente_flet_consulta_perfil_da_run_antes_de_abrir() -> None:
    session = FakeSession(
        [
            FakeResponse(
                200,
                {
                    "completed": True,
                    "preferred_name": "Janio",
                    "story_gender": "Como homem",
                },
            )
        ]
    )
    client = FletApiClient("https://api.example.com", session=session)  # type: ignore[arg-type]
    client.access_token = "token"

    profile = client.run_profile("roleplay2026.camilly")

    assert profile.completed is True
    assert profile.preferred_name == "Janio"
    assert profile.story_gender == "Como homem"
    assert session.calls[0][0] == "GET"
    assert session.calls[0][1].endswith(
        "/api/v1/runs/roleplay2026.camilly/profile"
    )


def test_cliente_flet_abre_e_avanca_run_real() -> None:
    first = {
        "run_id": "run-1",
        "package_id": "roleplay2026.camilly",
        "frame_id": "quadro-1",
        "content": "[QUADRO quadro-1]\n[DESCRIÇÃO]\nCena.\n[/QUADRO]",
        "image_url": "https://api.example.com/api/v1/runs/image",
        "entry_image_urls": [
            "https://api.example.com/api/v1/runs/image?image_id=mary1.webp"
        ],
        "revealed_entries": 0,
        "entry_count": 0,
        "finished": False,
    }
    session = FakeSession(
        [FakeResponse(200, first), FakeResponse(200, {**first, "frame_id": "quadro-2"})]
    )
    client = FletApiClient("https://api.example.com", session=session)  # type: ignore[arg-type]
    client.access_token = "token"

    opened = client.open_run(
        "roleplay2026.camilly",
        preferred_name="Janio",
        story_gender="Como homem",
    )
    advanced = client.advance_run(
        package_id=opened.package_id,
        frame_id=opened.frame_id,
        revealed_entries=opened.entry_count,
        preferred_name="Janio",
        story_gender="Como homem",
    )

    assert opened.run_id == "run-1"
    assert opened.entry_image_urls == (
        "https://api.example.com/api/v1/runs/image?image_id=mary1.webp",
    )
    assert advanced.frame_id == "quadro-2"
    assert session.calls[0][2]["json"] == {
        "package_id": "roleplay2026.camilly",
        "preferred_name": "Janio",
        "story_gender": "Como homem",
    }
    assert session.calls[1][2]["json"]["frame_id"] == "quadro-1"
    assert session.calls[1][2]["json"]["preferred_name"] == "Janio"
    assert session.calls[1][2]["json"]["story_gender"] == "Como homem"


def test_cliente_web_publica_imagens_da_run_recebidas_pelo_loopback() -> None:
    frame = {
        "run_id": "run-1",
        "package_id": "roleplay2026.camilly",
        "frame_id": "quadro-1",
        "content": "[QUADRO quadro-1]\n[DESCRIÇÃO]\nCena.\n[/QUADRO]",
        "image_url": "http://127.0.0.1:10000/api/v1/runs/image?node_id=quadro-1",
        "entry_image_urls": [
            "http://127.0.0.1:10000/api/v1/runs/image?image_id=mary1.webp"
        ],
        "revealed_entries": 0,
        "entry_count": 1,
        "finished": False,
    }
    client = FletApiClient(
        "http://127.0.0.1:10000",
        public_base_url="https://entrecenas-roleplay.com.br",
        session=FakeSession([FakeResponse(200, frame)]),  # type: ignore[arg-type]
    )

    opened = client.open_run(
        "roleplay2026.camilly",
        preferred_name="Janio",
        story_gender="Como homem",
    )

    assert opened.image_url.startswith(
        "https://entrecenas-roleplay.com.br/api/v1/runs/image"
    )
    assert opened.entry_image_urls[0].startswith(
        "https://entrecenas-roleplay.com.br/api/v1/runs/image"
    )
