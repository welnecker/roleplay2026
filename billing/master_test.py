from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from billing.v2_credit_grant import StoryCreditGrantRepository
from persistence.accounts import GoogleSheetsAccountRepository
from persistence.models import utc_now_iso
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def parse_master_emails(raw: str | Iterable[str]) -> frozenset[str]:
    values = raw.split(",") if isinstance(raw, str) else raw
    return frozenset(normalize_email(value) for value in values if normalize_email(value))


@dataclass(frozen=True, slots=True)
class MasterTestResult:
    stored: StoredPaymentOrder
    payment_id: str


class MasterTestPaymentService:
    """Pagamento sintético auditável, restrito à identidade persistida do master."""

    def __init__(
        self,
        *,
        accounts: GoogleSheetsAccountRepository,
        payments: GoogleSheetsPaymentRepository,
        story_credits: StoryCreditGrantRepository,
        master_emails: str | Iterable[str],
    ) -> None:
        self.accounts = accounts
        self.payments = payments
        self.story_credits = story_credits
        self.master_emails = parse_master_emails(master_emails)

    def is_authorized(self, *, user_id: str) -> bool:
        user = self.accounts.get_user(user_id=user_id)
        return bool(
            user
            and user.status == "active"
            and normalize_email(user.email) in self.master_emails
        )

    def approve_test_payment(
        self,
        *,
        user_id: str,
        package_id: str,
        amount_cents: int,
        currency: str,
    ) -> MasterTestResult:
        user = self.accounts.get_user(user_id=user_id)
        if (
            user is None
            or user.status != "active"
            or normalize_email(user.email) not in self.master_emails
        ):
            raise PermissionError("Usuário não autorizado para pagamento de teste.")
        if amount_cents <= 0:
            raise ValueError("O valor de teste deve ser maior que zero.")

        external_reference = f"rp26_test_{uuid4().hex}"
        payment_id = f"test_master_{uuid4().hex}"
        stored = self.payments.create_pending_order(
            user_id=user.user_id,
            package_id=package_id,
            product_id=package_id,
            amount_cents=amount_cents,
            currency=currency,
            payer_email_normalized=normalize_email(user.email),
            payment_mode="test_master",
            provider="test_master",
            external_reference=external_reference,
            idempotency_key=str(uuid4()),
        )
        stored = self.payments.update_provider_order(
            payment_order_id=stored.payment_order_id,
            provider_order_id=payment_id,
            status="approved",
            status_detail="master_test_approved",
            qr_code="",
            ticket_url="",
            validation_status="valid",
            approved_at=utc_now_iso(),
            raw={
                "mode": "test_master",
                "payment_id": payment_id,
                "external_reference": external_reference,
                "amount_cents": amount_cents,
                "currency": currency,
            },
        )
        self.story_credits.create_credit(
            user_id=user.user_id,
            package_id=package_id,
            payment_id=payment_id,
        )
        return MasterTestResult(stored=stored, payment_id=payment_id)
