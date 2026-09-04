from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.web_client_routes import install


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
