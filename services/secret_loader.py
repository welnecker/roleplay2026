from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any


def load_application_secrets() -> dict[str, Any]:
    """Carrega secrets.toml e variáveis de ambiente do servidor.

    O arquivo local é opcional e nunca deve ser versionado. Em provedores como
    Render, a conta de serviço do Google pode ser fornecida inteira em
    ``GCP_SERVICE_ACCOUNT_JSON`` ou campo a campo com o prefixo ``GCP_``.
    """

    result: dict[str, Any] = {}
    path = Path(os.getenv("STREAMLIT_SECRETS_FILE", ".streamlit/secrets.toml"))
    if path.is_file():
        with path.open("rb") as handle:
            result.update(tomllib.load(handle))

    aliases = (
        "GOOGLE_SHEETS_SPREADSHEET_ID",
        "ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID",
        "ROLEPLAY_RUNTIME_SPREADSHEET_ID",
        "ROLEPLAY_EDITORIAL_SPREADSHEET_ID",
        "V2_SHEETS_ADMIN_TOKEN",
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

    service_account = _service_account_from_environment()
    if service_account:
        result["gcp_service_account"] = service_account

    return result


def _service_account_from_environment() -> dict[str, str]:
    raw_json = os.getenv("GCP_SERVICE_ACCOUNT_JSON", "").strip()
    if raw_json:
        try:
            loaded = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON contém JSON inválido.") from exc
        if not isinstance(loaded, dict):
            raise RuntimeError("GCP_SERVICE_ACCOUNT_JSON deve representar um objeto JSON.")
        return {str(key): str(value) for key, value in loaded.items()}

    field_map = {
        "type": "GCP_TYPE",
        "project_id": "GCP_PROJECT_ID",
        "private_key_id": "GCP_PRIVATE_KEY_ID",
        "private_key": "GCP_PRIVATE_KEY",
        "client_email": "GCP_CLIENT_EMAIL",
        "client_id": "GCP_CLIENT_ID",
        "auth_uri": "GCP_AUTH_URI",
        "token_uri": "GCP_TOKEN_URI",
        "auth_provider_x509_cert_url": "GCP_AUTH_PROVIDER_X509_CERT_URL",
        "client_x509_cert_url": "GCP_CLIENT_X509_CERT_URL",
    }
    values = {
        field: os.getenv(environment_name, "").strip()
        for field, environment_name in field_map.items()
    }
    if not any(values.values()):
        return {}

    values["private_key"] = values["private_key"].replace("\\n", "\n")
    values["type"] = values["type"] or "service_account"
    values["auth_uri"] = values["auth_uri"] or "https://accounts.google.com/o/oauth2/auth"
    values["token_uri"] = values["token_uri"] or "https://oauth2.googleapis.com/token"
    values["auth_provider_x509_cert_url"] = (
        values["auth_provider_x509_cert_url"]
        or "https://www.googleapis.com/oauth2/v1/certs"
    )
    return {key: value for key, value in values.items() if value}
