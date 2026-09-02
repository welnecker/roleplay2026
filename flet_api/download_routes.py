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
DOWNLOAD_FILENAME = "entrecenas-roleplay.apk"
DOWNLOAD_MEDIA_TYPE = "application/vnd.android.package-archive"
DOWNLOAD_CHUNK_SIZE = 1024 * 1024


def download_page_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0c2e2d">
  <title>Baixar EntreCenas para Android</title>
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
    .button {
      display: block;
      margin: 28px 0 22px;
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
    <h1>EntreCenas para Android</h1>
    <p>Baixe a versão mais recente do EntreCenas diretamente pela página oficial.</p>
    <a class="button" href="/baixar/android">Baixar EntreCenas</a>
    <div class="info">
      <div><strong>Tamanho aproximado:</strong> 135 MB</div>
      <div>O download pode levar alguns minutos, dependendo da sua conexão.</div>
      <div>Quando concluir, toque no arquivo baixado para iniciar a instalação.</div>
    </div>
    <p class="note">O Android pode exibir avisos ao instalar aplicativos baixados fora da loja. Antes de continuar, confirme que você está em entrecenas-roleplay.com.br.</p>
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


def _download_headers(upstream: requests.Response) -> dict[str, str]:
    headers = {
        "Content-Disposition": f'attachment; filename="{DOWNLOAD_FILENAME}"',
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

    @app.get("/baixar/android", include_in_schema=False)
    def download_android(request: Request) -> StreamingResponse:
        try:
            upstream = requests.get(
                ANDROID_RELEASE_URL,
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
                detail=f"A versão para Android não está disponível no momento ({status_code}).",
            )

        return StreamingResponse(
            _stream_upstream(upstream),
            status_code=upstream.status_code,
            media_type=DOWNLOAD_MEDIA_TYPE,
            headers=_download_headers(upstream),
        )

    app.state.download_routes_installed = True
    return app
