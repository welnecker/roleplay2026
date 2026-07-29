from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any


def load_application_secrets() -> dict[str, Any]:
    """Carrega variáveis de ambiente e, quando disponível, secrets.toml.

    O arquivo é lido somente no servidor e nunca deve ser versionado.
    """
    result: dict[str, Any] = {}
    path = Path(os.getenv("STREAMLIT_SECRETS_FILE", ".streamlit/secrets.toml"))
    if path.is_file():
        with path.open("rb") as handle:
            result.update(tomllib.load(handle))

    aliases = (
        "GOOGLE_SHEETS_SPREADSHEET_ID",
        "MERCADO_PAGO_ACCESS_TOKEN",
        "MERCADOPAGO_ACCESS_TOKEN",
        "MP_ACCESS_TOKEN",
        "MERCADO_PAGO_WEBHOOK_SECRET",
        "MERCADOPAGO_WEBHOOK_SECRET",
        "MP_WEBHOOK_SECRET",
    )
    for name in aliases:
        value = os.getenv(name)
        if value:
            result[name] = value
    return result
