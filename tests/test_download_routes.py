from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.download_routes import ANDROID_RELEASE_URL, DOWNLOAD_FILENAME, install


class FakeUpstream:
    def __init__(
        self,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        chunks: tuple[bytes, ...] = (b"abc", b"def"),
    ) -> None:
        self.status_code = status_code
        self.headers = headers or {}
        self._chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size: int):
        assert chunk_size > 0
        yield from self._chunks

    def close(self) -> None:
        self.closed = True


def test_download_page_uses_user_friendly_language() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/baixar")

    assert response.status_code == 200
    assert "EntreCenas" in response.text
    assert 'href="/baixar/android"' in response.text
    assert "Baixar EntreCenas" in response.text
    assert "br.com.entrecenas.roleplay" not in response.text
    assert "Baixar APK" not in response.text


def test_android_download_streams_release_with_attachment_headers(monkeypatch) -> None:
    upstream = FakeUpstream(
        headers={
            "content-length": "6",
            "accept-ranges": "bytes",
            "etag": '"abc123"',
        }
    )
    observed: dict[str, object] = {}

    def fake_get(url: str, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return upstream

    monkeypatch.setattr("flet_api.download_routes.requests.get", fake_get)

    app = install(FastAPI())
    response = TestClient(app).get("/baixar/android")

    assert response.status_code == 200
    assert response.content == b"abcdef"
    assert observed["url"] == ANDROID_RELEASE_URL
    assert observed["stream"] is True
    assert observed["allow_redirects"] is True
    assert observed["headers"] == {"Accept-Encoding": "identity"}
    assert response.headers["content-length"] == "6"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="{DOWNLOAD_FILENAME}"'
    )
    assert upstream.closed is True


def test_android_download_forwards_range_and_partial_response(monkeypatch) -> None:
    upstream = FakeUpstream(
        status_code=206,
        headers={
            "content-length": "3",
            "content-range": "bytes 3-5/6",
            "accept-ranges": "bytes",
        },
        chunks=(b"def",),
    )
    observed: dict[str, object] = {}

    def fake_get(url: str, **kwargs):
        observed.update(kwargs)
        return upstream

    monkeypatch.setattr("flet_api.download_routes.requests.get", fake_get)

    app = install(FastAPI())
    response = TestClient(app).get(
        "/baixar/android",
        headers={"Range": "bytes=3-5"},
    )

    assert response.status_code == 206
    assert response.content == b"def"
    assert observed["headers"] == {
        "Accept-Encoding": "identity",
        "Range": "bytes=3-5",
    }
    assert response.headers["content-range"] == "bytes 3-5/6"


def test_download_routes_install_is_idempotent() -> None:
    app = FastAPI()
    install(app)
    install(app)

    paths = [route.path for route in app.routes]
    assert paths.count("/baixar") == 1
    assert paths.count("/baixar/android") == 1
