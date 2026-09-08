from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

import requests

API_BASE_URL = "https://api.mercadopago.com"


class MercadoPagoError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PixOrder:
    order_id: str
    status: str
    status_detail: str
    external_reference: str
    qr_code: str
    qr_code_base64: str
    ticket_url: str
    amount_cents: int
    currency: str
    raw: dict[str, Any]

    @property
    def approved(self) -> bool:
        payment = _first_payment(self.raw)
        payment_status = str(payment.get("status", "")).lower()
        payment_detail = str(payment.get("status_detail", "")).lower()
        order_status = self.status.lower()
        order_detail = self.status_detail.lower()
        return (
            order_status == "approved"
            or payment_status == "approved"
            or (order_status == "processed" and order_detail == "accredited")
            or (payment_status == "processed" and payment_detail == "accredited")
        )


class MercadoPagoClient:
    def __init__(self, access_token: str, *, timeout: float = 20.0) -> None:
        token = access_token.strip()
        if not token:
            raise ValueError("Access Token do Mercado Pago não configurado.")
        self.access_token = token
        self.timeout = timeout

    def create_pix_order(
        self,
        *,
        amount_cents: int,
        external_reference: str,
        payer_email: str,
        description: str,
        idempotency_key: str | None = None,
        expiration_time: str = "PT30M",
    ) -> PixOrder:
        del description  # O título permanece no catálogo; a Orders API não exige descrição.
        if amount_cents <= 0:
            raise ValueError("O valor da cobrança deve ser maior que zero.")
        amount = Decimal(amount_cents) / Decimal(100)
        payload = {
            "type": "online",
            "total_amount": f"{amount:.2f}",
            "external_reference": external_reference,
            "processing_mode": "automatic",
            "transactions": {
                "payments": [
                    {
                        "amount": f"{amount:.2f}",
                        "payment_method": {"id": "pix", "type": "bank_transfer"},
                        "expiration_time": expiration_time,
                    }
                ]
            },
            "payer": {"email": payer_email},
        }
        data = self._request(
            "POST",
            "/v1/orders",
            json=payload,
            idempotency_key=idempotency_key or str(uuid4()),
        )
        return parse_pix_order(data)

    def get_order(self, order_id: str) -> PixOrder:
        data = self._request("GET", f"/v1/orders/{order_id}")
        return parse_pix_order(data)

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        try:
            response = requests.request(
                method,
                f"{API_BASE_URL}{path}",
                headers=headers,
                json=json,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise MercadoPagoError(f"Falha de conexão com o Mercado Pago: {exc}") from exc
        try:
            data = response.json()
        except ValueError:
            data = {"message": response.text}
        if response.status_code >= 400:
            message = data.get("message") or data.get("error") or response.text
            raise MercadoPagoError(f"Mercado Pago retornou HTTP {response.status_code}: {message}")
        if not isinstance(data, dict):
            raise MercadoPagoError("Resposta inválida do Mercado Pago.")
        return data


def parse_pix_order(data: dict[str, Any]) -> PixOrder:
    payment = _first_payment(data)
    method = payment.get("payment_method") if isinstance(payment.get("payment_method"), dict) else {}
    raw_amount = payment.get("amount", data.get("total_amount", "0"))
    try:
        amount_cents = int((Decimal(str(raw_amount)) * Decimal(100)).quantize(Decimal("1")))
    except Exception:
        amount_cents = 0
    currency = str(
        payment.get("currency_id")
        or payment.get("currency")
        or data.get("currency_id")
        or data.get("currency")
        or "BRL"
    ).upper()
    return PixOrder(
        order_id=str(data.get("id", "")),
        status=str(data.get("status", payment.get("status", ""))),
        status_detail=str(data.get("status_detail", payment.get("status_detail", ""))),
        external_reference=str(data.get("external_reference", "")),
        qr_code=str(method.get("qr_code", "")),
        qr_code_base64=str(method.get("qr_code_base64", "")),
        ticket_url=str(method.get("ticket_url", "")),
        amount_cents=amount_cents,
        currency=currency,
        raw=data,
    )


def _first_payment(data: dict[str, Any]) -> dict[str, Any]:
    transactions = data.get("transactions")
    if not isinstance(transactions, dict):
        return {}
    payments = transactions.get("payments")
    if not isinstance(payments, list) or not payments or not isinstance(payments[0], dict):
        return {}
    return payments[0]


def validate_webhook_signature(
    *,
    x_signature: str,
    x_request_id: str,
    data_id: str,
    secret: str,
) -> bool:
    parts: dict[str, str] = {}
    for item in x_signature.split(","):
        key, separator, value = item.strip().partition("=")
        if separator:
            parts[key] = value
    timestamp = parts.get("ts", "")
    received = parts.get("v1", "")
    if not timestamp or not received or not secret:
        return False
    manifest_parts: list[str] = []
    if data_id:
        manifest_parts.append(f"id:{data_id};")
    if x_request_id:
        manifest_parts.append(f"request-id:{x_request_id};")
    manifest_parts.append(f"ts:{timestamp};")
    calculated = hmac.new(
        secret.encode("utf-8"),
        "".join(manifest_parts).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(calculated, received)
