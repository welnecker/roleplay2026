from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from billing.mercado_pago import MercadoPagoClient, PixOrder
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    stored: StoredPaymentOrder
    provider: PixOrder


def read_secret(secrets: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = secrets.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    mercado_pago = secrets.get("mercado_pago")
    if isinstance(mercado_pago, Mapping):
        for name in names:
            key = name.lower().removeprefix("mercado_pago_")
            value = mercado_pago.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""


class PixCheckoutService:
    def __init__(
        self,
        *,
        client: MercadoPagoClient,
        payments: GoogleSheetsPaymentRepository,
        accounts: GoogleSheetsAccountRepository,
    ) -> None:
        self.client = client
        self.payments = payments
        self.accounts = accounts

    def create_checkout(
        self,
        *,
        user_id: str,
        payer_email: str,
        package_id: str,
        product_id: str,
        title: str,
        amount_cents: int,
        currency: str,
    ) -> CheckoutResult:
        external_reference = f"roleplay2026:{user_id}:{package_id}:{uuid4().hex}"
        idempotency_key = str(uuid4())
        stored = self.payments.create_pending_order(
            user_id=user_id,
            package_id=package_id,
            product_id=product_id,
            amount_cents=amount_cents,
            currency=currency,
            external_reference=external_reference,
            idempotency_key=idempotency_key,
        )
        provider = self.client.create_pix_order(
            amount_cents=amount_cents,
            external_reference=external_reference,
            payer_email=payer_email,
            description=title,
            idempotency_key=idempotency_key,
        )
        stored = self.payments.update_provider_order(
            payment_order_id=stored.payment_order_id,
            provider_order_id=provider.order_id,
            status=provider.status,
            status_detail=provider.status_detail,
            qr_code=provider.qr_code,
            ticket_url=provider.ticket_url,
            raw=provider.raw,
        )
        if provider.approved:
            self._grant(stored, provider)
        return CheckoutResult(stored=stored, provider=provider)

    def refresh(self, stored: StoredPaymentOrder) -> CheckoutResult:
        provider = self.client.get_order(stored.provider_order_id)
        updated = self.payments.update_provider_order(
            payment_order_id=stored.payment_order_id,
            provider_order_id=provider.order_id,
            status=provider.status,
            status_detail=provider.status_detail,
            qr_code=provider.qr_code or stored.qr_code,
            ticket_url=provider.ticket_url or stored.ticket_url,
            raw=provider.raw,
        )
        if provider.approved:
            self._grant(updated, provider)
        return CheckoutResult(stored=updated, provider=provider)

    def process_provider_order(self, provider_order_id: str) -> CheckoutResult | None:
        stored = self.payments.find_by_provider_order_id(provider_order_id)
        if stored is None:
            return None
        return self.refresh(stored)

    def _grant(self, stored: StoredPaymentOrder, provider: PixOrder) -> None:
        self.accounts.grant_entitlement(
            user_id=stored.user_id,
            package_id=stored.package_id,
            product_id=stored.product_id,
            source="mercado_pago_pix",
            payment_id=provider.order_id,
        )
