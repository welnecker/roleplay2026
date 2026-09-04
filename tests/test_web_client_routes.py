from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.web_client_routes import install, internal_api_url


def test_web_client_uses_render_loopback_api(monkeypatch) -> None:
    monkeypatch.delenv("ROLEPLAY_FLET_INTERNAL_API_URL", raising=False)
    monkeypatch.setenv("PORT", "12345")

    assert internal_api_url() == "http://127.0.0.1:12345"


def test_web_client_internal_api_can_be_overridden(monkeypatch) -> None:
    monkeypatch.setenv("ROLEPLAY_FLET_INTERNAL_API_URL", " http://api:9000/ ")

    assert internal_api_url() == "http://api:9000"


def test_web_client_is_available_under_app_path() -> None:
    app = install(FastAPI())

    with TestClient(app) as client:
        response = client.get("/app/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert b"flutter_bootstrap.js" in response.content


def test_web_client_install_is_idempotent() -> None:
    app = FastAPI()
    install(app)
    install(app)

    assert [route.path for route in app.routes].count("/app") == 1
