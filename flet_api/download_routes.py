from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import requests
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse


ANDROID_PACKAGE_ID = "br.com.entrecenas.roleplay"
ANDROID_RELEASE_URL = (
    "https://github.com/welnecker/roleplay2026/"
    "releases/latest/download/entrecenas-roleplay.apk"
)
WINDOWS_RELEASE_URL = (
    "https://github.com/welnecker/roleplay2026/"
    "releases/latest/download/entrecenas-windows.zip"
)
ANDROID_DOWNLOAD_FILENAME = "entrecenas-roleplay.apk"
WINDOWS_DOWNLOAD_FILENAME = "entrecenas-windows.zip"
ANDROID_DOWNLOAD_MEDIA_TYPE = "application/vnd.android.package-archive"
WINDOWS_DOWNLOAD_MEDIA_TYPE = "application/zip"
# Compatibilidade com consumidores que importavam os nomes anteriores.
DOWNLOAD_FILENAME = ANDROID_DOWNLOAD_FILENAME
DOWNLOAD_MEDIA_TYPE = ANDROID_DOWNLOAD_MEDIA_TYPE
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def download_page_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0c2e2d">
  <title>Baixar EntreCenas</title>
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #071918;
      color: #f7f7f2;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    main {
      width: min(100%, 620px);
      background: #0c2e2d;
      border: 1px solid #24504e;
      border-radius: 24px;
      padding: clamp(24px, 6vw, 44px);
      box-shadow: 0 24px 70px rgba(0, 0, 0, .35);
    }
    .brand { font-size: 1.05rem; font-weight: 700; color: #f05b91; }
    h1 { margin: 10px 0 14px; font-size: clamp(2rem, 8vw, 3rem); line-height: 1.05; }
    p { line-height: 1.6; color: #d8e3e2; }
    .downloads { display: grid; gap: 14px; margin: 28px 0 22px; }
    .button {
      display: block;
      padding: 16px 20px;
      border-radius: 999px;
      background: #f05b91;
      color: #fff;
      text-decoration: none;
      text-align: center;
      font-weight: 800;
      font-size: 1.05rem;
    }
    .info {
      display: grid;
      gap: 8px;
      padding: 16px;
      border-radius: 14px;
      background: rgba(255,255,255,.06);
      font-size: .94rem;
      line-height: 1.5;
      color: #d8e3e2;
    }
    .info strong { color: #fff; }
    .note { font-size: .9rem; color: #b9cac9; }
  </style>
</head>
<body>
  <main>
    <div class="brand">EntreCenas</div>
    <h1>Escolha seu dispositivo</h1>
    <p>Baixe a versão mais recente do EntreCenas diretamente pela página oficial.</p>
    <div class="downloads">
      <a class="button" href="/baixar/android">Instalar no Android</a>
      <a class="button" href="/baixar/windows">Baixar para Windows</a>
    </div>
    <div class="info">
      <div>O download pode levar alguns minutos, dependendo da sua conexão.</div>
      <div>No Android, toque no arquivo baixado para iniciar a instalação.</div>
      <div>No Windows, extraia o pacote e abra o EntreCenas.</div>
    </div>
    <p class="note">O sistema pode exibir um aviso para aplicativos baixados fora da loja. Antes de continuar, confirme que você está em entrecenas-roleplay.com.br.</p>
  </main>
</body>
</html>
"""


def _stream_upstream(response: requests.Response) -> Iterator[bytes]:
    try:
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
            if chunk:
                yield chunk
    finally:
        response.close()


def _upstream_headers(request: Request) -> dict[str, str]:
    headers = {"Accept-Encoding": "identity"}
    range_header = request.headers.get("range")
    if range_header:
        headers["Range"] = range_header
    return headers


def _download_headers(upstream: requests.Response, filename: str) -> dict[str, str]:
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
    for source, target in (
        ("content-length", "Content-Length"),
        ("content-range", "Content-Range"),
        ("accept-ranges", "Accept-Ranges"),
        ("etag", "ETag"),
        ("last-modified", "Last-Modified"),
    ):
        value = upstream.headers.get(source)
        if value:
            headers[target] = value
    return headers


def install(app: Any) -> Any:
    """Instala as rotas públicas de distribuição sem tocar nas APIs autenticadas."""

    if getattr(app.state, "download_routes_installed", False):
        return app

    @app.get("/baixar", response_class=HTMLResponse, include_in_schema=False)
    def download_page() -> HTMLResponse:
        return HTMLResponse(download_page_html())

    def stream_release(
        request: Request,
        *,
        release_url: str,
        filename: str,
        media_type: str,
        platform_name: str,
    ) -> StreamingResponse:
        try:
            upstream = requests.get(
                release_url,
                headers=_upstream_headers(request),
                stream=True,
                allow_redirects=True,
                timeout=(10, 120),
            )
        except requests.RequestException as exc:
            raise HTTPException(
                status_code=502,
                detail="Não foi possível iniciar o download. Tente novamente em instantes.",
            ) from exc

        if upstream.status_code not in {200, 206}:
            status_code = upstream.status_code
            upstream.close()
            raise HTTPException(
                status_code=502,
                detail=f"A versão para {platform_name} não está disponível no momento ({status_code}).",
            )

        return StreamingResponse(
            _stream_upstream(upstream),
            status_code=upstream.status_code,
            media_type=media_type,
            headers=_download_headers(upstream, filename),
        )

    @app.get("/baixar/android", include_in_schema=False)
    def download_android(request: Request) -> StreamingResponse:
        return stream_release(
            request,
            release_url=ANDROID_RELEASE_URL,
            filename=ANDROID_DOWNLOAD_FILENAME,
            media_type=ANDROID_DOWNLOAD_MEDIA_TYPE,
            platform_name="Android",
        )

    @app.get("/baixar/windows", include_in_schema=False)
    def download_windows(request: Request) -> StreamingResponse:
        return stream_release(
            request,
            release_url=WINDOWS_RELEASE_URL,
            filename=WINDOWS_DOWNLOAD_FILENAME,
            media_type=WINDOWS_DOWNLOAD_MEDIA_TYPE,
            platform_name="Windows",
        )

    app.state.download_routes_installed = True
    return app
