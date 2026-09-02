from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.download_routes import ANDROID_RELEASE_URL, install


def test_download_page_uses_clear_user_facing_android_language() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/baixar")

    assert response.status_code == 200
    assert "EntreCenas para Android" in response.text
    assert "Baixar EntreCenas" in response.text
    assert "Tamanho aproximado:" in response.text
    assert "135 MB" in response.text
    assert "Ao chegar a 100%" in response.text
    assert "br.com.entrecenas.roleplay" not in response.text
    assert "Baixar APK" not in response.text
    assert 'href="/baixar/android"' in response.text


def test_android_download_redirects_to_latest_public_release() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/baixar/android", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == ANDROID_RELEASE_URL
    assert ANDROID_RELEASE_URL.endswith(
        "/releases/latest/download/entrecenas-roleplay.apk"
    )


def test_download_routes_install_is_idempotent() -> None:
    app = FastAPI()
    install(app)
    install(app)

    paths = [route.path for route in app.routes]
    assert paths.count("/baixar") == 1
    assert paths.count("/baixar/android") == 1
