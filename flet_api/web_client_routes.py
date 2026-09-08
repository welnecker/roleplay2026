from __future__ import annotations

from contextlib import asynccontextmanager
import os
from typing import Any

import flet as ft
import flet.fastapi as flet_fastapi

from flet_client.main import configured_api_url, main as flet_main


WEB_APP_PATH = "/app"


def internal_api_url() -> str:
    """Mantém o tráfego do cliente web dentro da instância do Render."""

    configured = str(os.getenv("ROLEPLAY_FLET_INTERNAL_API_URL", "") or "").strip()
    if configured:
        return configured.rstrip("/")
    port = str(os.getenv("PORT", "10000") or "10000").strip()
    return f"http://127.0.0.1:{port}"


async def web_main(page: ft.Page) -> None:
    await flet_main(
        page,
        api_url_override=internal_api_url(),
        api_url_label=configured_api_url(),
    )


def install(app: Any) -> Any:
    """Monta o cliente Flet web sem duplicar API, login ou estado autoritativo."""

    if getattr(app.state, "web_client_routes_installed", False):
        return app

    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app_instance: Any):
        await flet_fastapi.app_manager.start()
        try:
            async with previous_lifespan(app_instance):
                yield
        finally:
            await flet_fastapi.app_manager.shutdown()

    app.router.lifespan_context = lifespan

    app.mount(
        WEB_APP_PATH,
        flet_fastapi.app(
            web_main,
            assets_dir="assets",
            app_name="EntreCenas",
            app_short_name="EntreCenas",
            app_description="Histórias interativas para adultos",
            session_timeout_seconds=3600,
        ),
        name="entrecenas-web",
    )
    app.state.web_client_routes_installed = True
    return app
