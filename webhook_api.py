from __future__ import annotations

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
