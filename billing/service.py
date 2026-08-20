from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping
from uuid import uuid4

from billing.mercado_pago import MercadoPagoClient, MercadoPagoError, PixOrder
from billing.v2_credit_grant import StoryCreditGrantRepository
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.models import utc_now_iso
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder


@dataclass(frozen=True, slots=True)
class CheckoutResult:
    stored: StoredPaymentOrder
    provider: PixOrder


class PaymentValidationError(RuntimeError):
    """Pagamento aprovado pelo provedor, mas incompatível com a ordem interna."""


def validate_approved_order(stored: StoredPaymentOrder, provider: PixOrder) -> None:
    if not provider.approved:
        raise PaymentValidationError("Pagamento ainda não foi aprovado pelo provedor.")
    if provider.order_id != stored.provider_order_id:
        raise PaymentValidationError("Identificador externo divergente.")
    if provider.external_reference != stored.external_reference:
        raise PaymentValidationError("Referência externa divergente.")
    if provider.amount_cents != stored.amount_cents:
        raise PaymentValidationError("Valor aprovado divergente.")
    if provider.currency.upper() != stored.currency.upper():
        raise PaymentValidationError("Moeda aprovada divergente.")
    if stored.product_id != stored.package_id:
        raise PaymentValidationError("Produto e pacote da ordem são divergentes.")


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


class PixCheckoutService:
    def __init__(
        self,
        *,
        client: MercadoPagoClient,
        payments: GoogleSheetsPaymentRepository,
        accounts: GoogleSheetsAccountRepository | None = None,
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
        if self.client.access_token.strip().upper().startswith("TEST-"):
            raise MercadoPagoError(
                "Credencial sandbox não pode criar cobranças no fluxo Pix real."
            )
        provider_payer_email = payer_email.strip().casefold()
        if self.accounts is not None:
            account = self.accounts.get_user(user_id=user_id)
            if account is None or account.status != "active":
                raise PermissionError("Conta de pagamento inexistente ou inativa.")
            provider_payer_email = account.email.strip().casefold()
        stored = self.payments.create_pending_order(
            user_id=user_id,
            package_id=package_id,
            product_id=product_id,
            amount_cents=amount_cents,
            currency=currency,
            payer_email_normalized=provider_payer_email,
            payment_mode="real_pix",
            provider="mercado_pago",
            external_reference=external_reference,
            idempotency_key=idempotency_key,
        )
        provider = self.client.create_pix_order(
            amount_cents=amount_cents,
            external_reference=external_reference,
            payer_email=provider_payer_email,
            description=title,
            idempotency_key=idempotency_key,
        )
        if provider.approved:
            validate_approved_order(
                replace(stored, provider_order_id=provider.order_id), provider
            )
        stored = self.payments.update_provider_order(
            payment_order_id=stored.payment_order_id,
            provider_order_id=provider.order_id,
            status=provider.status,
            status_detail=provider.status_detail,
            qr_code=provider.qr_code,
            ticket_url=provider.ticket_url,
            raw=provider.raw,
            validation_status="valid" if provider.approved else "pending",
            approved_at=utc_now_iso() if provider.approved else "",
        )
        if provider.approved:
            self._grant(stored, provider)
        return CheckoutResult(stored=stored, provider=provider)

    def refresh(self, stored: StoredPaymentOrder) -> CheckoutResult:
        provider = self.client.get_order(stored.provider_order_id)
        if provider.approved:
            validate_approved_order(stored, provider)
        updated = self.payments.update_provider_order(
            payment_order_id=stored.payment_order_id,
            provider_order_id=provider.order_id,
            status=provider.status,
            status_detail=provider.status_detail,
            qr_code=provider.qr_code or stored.qr_code,
            ticket_url=provider.ticket_url or stored.ticket_url,
            raw=provider.raw,
            validation_status="valid" if provider.approved else "pending",
            approved_at=(stored.approved_at or utc_now_iso()) if provider.approved else "",
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
        validate_approved_order(stored, provider)
        # O fluxo v2 usa um crédito por execução. Quando o repositório de créditos
        # está configurado, não cria mais USER_ENTITLEMENTS no armazenamento legado.
        if self.story_credits is not None:
            self.story_credits.create_credit(
                user_id=stored.user_id,
                package_id=stored.package_id,
                payment_id=provider.order_id,
            )
            return

        if self.accounts is not None:
            self.accounts.grant_entitlement(
                user_id=stored.user_id,
                package_id=stored.package_id,
                product_id=stored.product_id,
                source="mercado_pago_pix",
                payment_id=provider.order_id,
            )
