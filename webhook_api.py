from __future__ import annotations

import os
import secrets as secrets_module
from pathlib import Path
from typing import Any

import gspread
from fastapi import FastAPI, Header, HTTPException, Query, Request

from billing.mercado_pago import MercadoPagoClient, validate_webhook_signature
from billing.service import PixCheckoutService, read_secret
from persistence.payments import GoogleSheetsPaymentRepository
from persistence.spreadsheet_config import read_spreadsheet_ids
from persistence.v2_google_sheets import GoogleSheetsStoryCreditRepository
from services.secret_loader import load_application_secrets
from services.v2_schema_initializer import initialize_v2_sheet_schemas


app = FastAPI(title="Roleplay 2026 Webhooks", version="0.4.0")


def build_services() -> tuple[PixCheckoutService, GoogleSheetsPaymentRepository, str]:
    secrets = load_application_secrets()
    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise RuntimeError("Google Sheets não configurado.")

    spreadsheet_ids = read_spreadsheet_ids(secrets)
    client = gspread.service_account_from_dict(dict(credentials))
    accounts_billing = client.open_by_key(spreadsheet_ids.accounts_billing)

    access_token = read_secret(
        secrets,
        "MERCADO_PAGO_ACCESS_TOKEN",
        "MERCADOPAGO_ACCESS_TOKEN",
        "MP_ACCESS_TOKEN",
    )
    webhook_secret = read_secret(
        secrets,
        "MERCADO_PAGO_WEBHOOK_SECRET",
        "MERCADOPAGO_WEBHOOK_SECRET",
        "MP_WEBHOOK_SECRET",
    )

    payments = GoogleSheetsPaymentRepository(accounts_billing)
    story_credits = GoogleSheetsStoryCreditRepository(accounts_billing)
    service = PixCheckoutService(
        client=MercadoPagoClient(access_token),
        payments=payments,
        story_credits=story_credits,
    )
    return service, payments, webhook_secret


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/config-status")
def config_status() -> dict[str, Any]:
    """Expõe apenas presença/ausência da configuração, nunca valores secretos."""

    configured_path = os.getenv("STREAMLIT_SECRETS_FILE", ".streamlit/secrets.toml")
    path = Path(configured_path)
    try:
        secrets = load_application_secrets()
        loader_error = ""
    except Exception as exc:
        secrets = {}
        loader_error = f"{type(exc).__name__}: {exc}"

    service_account = secrets.get("gcp_service_account")
    return {
        "status": "ok" if not loader_error else "configuration_error",
        "secrets_file_path": configured_path,
        "secrets_file_exists": path.is_file(),
        "spreadsheet_id_present": bool(
            str(secrets.get("GOOGLE_SHEETS_SPREADSHEET_ID", "") or "").strip()
        ),
        "accounts_billing_spreadsheet_id_present": bool(
            str(secrets.get("ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID", "") or "").strip()
        ),
        "runtime_spreadsheet_id_present": bool(
            str(secrets.get("ROLEPLAY_RUNTIME_SPREADSHEET_ID", "") or "").strip()
        ),
        "editorial_spreadsheet_id_present": bool(
            str(secrets.get("ROLEPLAY_EDITORIAL_SPREADSHEET_ID", "") or "").strip()
        ),
        "v2_sheets_admin_token_present": bool(
            str(secrets.get("V2_SHEETS_ADMIN_TOKEN", "") or "").strip()
        ),
        "service_account_section_present": isinstance(service_account, dict) and bool(service_account),
        "service_account_client_email_present": bool(
            isinstance(service_account, dict)
            and str(service_account.get("client_email", "") or "").strip()
        ),
        "mercado_pago_access_token_present": bool(
            read_secret(
                secrets,
                "MERCADO_PAGO_ACCESS_TOKEN",
                "MERCADOPAGO_ACCESS_TOKEN",
                "MP_ACCESS_TOKEN",
            )
        ),
        "mercado_pago_webhook_secret_present": bool(
            read_secret(
                secrets,
                "MERCADO_PAGO_WEBHOOK_SECRET",
                "MERCADOPAGO_WEBHOOK_SECRET",
                "MP_WEBHOOK_SECRET",
            )
        ),
        "loader_error": loader_error,
    }


@app.post("/admin/initialize-v2-sheets")
def initialize_v2_sheets_endpoint(
    x_admin_token: str = Header(default="", alias="x-admin-token"),
) -> dict[str, Any]:
    """Cria ou valida as abas v2 usando a configuração do Render."""

    application_secrets = load_application_secrets()
    expected_token = str(
        application_secrets.get("V2_SHEETS_ADMIN_TOKEN", "") or ""
    ).strip()
    supplied_token = x_admin_token.strip()
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="V2_SHEETS_ADMIN_TOKEN não está configurado.",
        )
    if not supplied_token or not secrets_module.compare_digest(
        supplied_token,
        expected_token,
    ):
        raise HTTPException(status_code=401, detail="Token administrativo inválido.")

    try:
        results = initialize_v2_sheet_schemas(application_secrets)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao inicializar as planilhas: {type(exc).__name__}",
        ) from exc

    return {
        "status": "ok",
        "spreadsheets": [
            {
                "name": result.spreadsheet_name,
                "created_sheets": list(result.created_sheets),
                "existing_sheets": list(result.existing_sheets),
            }
            for result in results
        ],
    }


@app.post("/webhooks/mercado-pago")
async def mercado_pago_webhook(
    request: Request,
    data_id: str = Query(default="", alias="data.id"),
    notification_type: str = Query(default="", alias="type"),
    x_signature: str = Header(default="", alias="x-signature"),
    x_request_id: str = Header(default="", alias="x-request-id"),
) -> dict[str, Any]:
    payload = await request.json()
    if not data_id and isinstance(payload, dict):
        data = payload.get("data")
        if isinstance(data, dict):
            data_id = str(data.get("id", ""))
    service, payments, webhook_secret = build_services()
    signature_valid = validate_webhook_signature(
        x_signature=x_signature,
        x_request_id=x_request_id,
        data_id=data_id,
        secret=webhook_secret,
    )
    provider_event_id = str(payload.get("id", "")) if isinstance(payload, dict) else ""
    event_type = str(payload.get("action", notification_type)) if isinstance(payload, dict) else notification_type
    payments.record_webhook(
        provider_event_id=provider_event_id,
        provider_order_id=data_id,
        event_type=event_type,
        signature_valid=signature_valid,
        payload=payload if isinstance(payload, dict) else {},
    )
    if not signature_valid:
        raise HTTPException(status_code=401, detail="Assinatura inválida.")
    if notification_type not in {"", "orders", "order"}:
        return {"received": True, "ignored": True}
    result = service.process_provider_order(data_id)
    return {
        "received": True,
        "processed": result is not None,
        "approved": bool(result and result.provider.approved),
    }
