from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import flet.fastapi as flet_fastapi

from flet_client.main import main as flet_main


WEB_APP_PATH = "/app"


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
            flet_main,
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
