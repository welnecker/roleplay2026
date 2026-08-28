from __future__ import annotations

import flet as ft

from flet_client.main import main


# Entrada web separada para Uvicorn/Render. Nenhum serviço de produção aponta
# para este módulo nesta fase; ele existe para testes e deploy futuro isolado.
app = ft.run(main, export_asgi_app=True)

