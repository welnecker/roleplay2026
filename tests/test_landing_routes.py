from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.landing_routes import install


def test_landing_page_presents_participant_positioning() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Você faz parte dela" in response.text
    assert "Descubra seu papel" in response.text
    assert "Você também é personagem" in response.text
    assert 'href="/baixar"' in response.text
    assert "Você decide o que acontece" not in response.text
    assert "Suas escolhas mudam" not in response.text


def test_landing_page_has_indexing_and_security_headers() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/")

    assert '<meta name="robots" content="index,follow">' in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_conhecer_serves_landing_without_redirect_or_download() -> None:
    app = install(FastAPI())
    client = TestClient(app)

    response = client.get("/conhecer", follow_redirects=False)

    assert response.status_code == 200
    assert response.history == []
    assert response.headers["content-type"].startswith("text/html")
    assert "content-disposition" not in response.headers
    assert "Você faz parte dela" in response.text
    assert 'href="/baixar"' in response.text
    assert 'href="/baixar/android"' not in response.text


def test_landing_media_routes_serve_packaged_assets() -> None:
    app = install(FastAPI())
    client = TestClient(app)

    reel = client.get("/midia/entrecenas-reel.mp4")
    poster = client.get("/midia/entrecenas-reel-poster.webp")
    icon = client.get("/midia/entrecenas-icone.svg")

    assert reel.status_code == 200
    assert reel.headers["content-type"].startswith("video/mp4")
    assert len(reel.content) > 1_000_000
    assert poster.status_code == 200
    assert poster.headers["content-type"].startswith("image/webp")
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/svg+xml")


def test_landing_routes_install_is_idempotent() -> None:
    app = FastAPI()
    install(app)
    install(app)

    paths = [route.path for route in app.routes]
    assert paths.count("/") == 1
    assert paths.count("/conhecer") == 1
    assert paths.count("/midia/entrecenas-reel.mp4") == 1
    assert paths.count("/midia/entrecenas-reel-poster.webp") == 1
    assert paths.count("/midia/entrecenas-icone.svg") == 1
