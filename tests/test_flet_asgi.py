from __future__ import annotations

from fastapi.testclient import TestClient

from flet_client.asgi import app


def test_frontend_flet_exporta_aplicacao_asgi() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert b"flutter_bootstrap.js" in response.content
