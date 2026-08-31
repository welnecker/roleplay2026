from __future__ import annotations

from flet_api.app import production_app
from persistence.sheets_audit import install as install_sheets_audit


# Entrada futura e independente. Nenhum serviço de produção aponta para ela.
app = install_sheets_audit(production_app())

