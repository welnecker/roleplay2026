from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping
from uuid import uuid4

from billing.mercado_pago import MercadoPagoClient, MercadoPagoError, PixOrder
from billing.v2_credit_grant import StoryCreditGrantRepository
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    stored: StoredPaymentOrder
    provider: PixOrder


def _streamlit_paid_access_resolver(*, user_id: str, package_id: str, access: str) -> bool:
    if access == "free":
        return True
    try:
        import streamlit as st

        from services.paid_run_access import get_paid_run_access

        return get_paid_run_access(
            secrets=st.secrets,
            user_id=user_id,
            package_id=package_id,
        ).allowed
    except Exception:
        return False


GoogleSheetsAccountRepository.configure_paid_access_resolver(_streamlit_paid_access_resolver)


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


def _new_external_reference() -> str:
    """Gera uma referência curta aceita pela API Orders do Mercado Pago."""

    return f"rp26_{uuid4().hex}"


def _sandbox_payer_email(user_id: str) -> str:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:24]
    return f"rp26_{digest}@testuser.com"


def _payer_email_for_environment(*, access_token: str, payer_email: str, user_id: str) -> str:
    """Adapta antecipadamente o e-mail para tokens TEST- conhecidos."""

    clean_email = payer_email.strip().lower()
    if clean_email.endswith("@testuser.com"):
        return clean_email
    if access_token.strip().upper().startswith("TEST-"):
        return _sandbox_payer_email(user_id)
    return clean_email


def _is_sandbox_email_error(exc: MercadoPagoError) -> bool:
    message = str(exc).lower()
    return "invalid_email_for_sandbox" in message or "@testuser.com" in message


class PixCheckoutService:
    def __init__(
        self,
        *,
        client: MercadoPagoClient,
        payments: GoogleSheetsPaymentRepository,
        accounts: GoogleSheetsAccountRepository,
        story_credits: StoryCreditGrantRepository | None = None,
    ) -> None:
        self.client = client
        self.payments = payments
        self.accounts = accounts
        self.story_credits = story_credits

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
        external_reference = _new_external_reference()
        idempotency_key = str(uuid4())
        provider_payer_email = _payer_email_for_environment(
            access_token=self.client.access_token,
            payer_email=payer_email,
            user_id=user_id,
        )
        stored = self.payments.create_pending_order(
            user_id=user_id,
            package_id=package_id,
            product_id=product_id,
            amount_cents=amount_cents,
            currency=currency,
            external_reference=external_reference,
            idempotency_key=idempotency_key,
        )
        try:
            provider = self.client.create_pix_order(
                amount_cents=amount_cents,
                external_reference=external_reference,
                payer_email=provider_payer_email,
                description=title,
                idempotency_key=idempotency_key,
            )
        except MercadoPagoError as exc:
            if not _is_sandbox_email_error(exc):
                raise
            provider = self.client.create_pix_order(
                amount_cents=amount_cents,
                external_reference=external_reference,
                payer_email=_sandbox_payer_email(user_id),
                description=title,
                idempotency_key=str(uuid4()),
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
        if self.story_credits is not None:
            self.story_credits.create_credit(
                user_id=stored.user_id,
                package_id=stored.package_id,
                payment_id=provider.order_id,
            )
