from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request

from billing.mercado_pago import MercadoPagoClient, validate_webhook_signature
from billing.service import PixCheckoutService, read_secret
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.factory import build_google_sheets_repository
from persistence.payments import GoogleSheetsPaymentRepository
from services.secret_loader import load_application_secrets


app = FastAPI(title="Roleplay 2026 Webhooks", version="0.1.0")


def build_services() -> tuple[PixCheckoutService, GoogleSheetsPaymentRepository, str]:
    secrets = load_application_secrets()
    runtime = build_google_sheets_repository(secrets)
    if runtime is None:
        raise RuntimeError("Google Sheets não configurado.")
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
    accounts = GoogleSheetsAccountRepository(runtime.spreadsheet)
    accounts.ensure_schema()
    payments = GoogleSheetsPaymentRepository(runtime.spreadsheet)
    payments.ensure_schema()
    service = PixCheckoutService(
        client=MercadoPagoClient(access_token),
        payments=payments,
        accounts=accounts,
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
    except Exception as exc:  # diagnóstico operacional sem revelar valores
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
