from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import gspread

from billing.master_test import MasterTestPaymentService
from billing.mercado_pago import MercadoPagoClient
from billing.service import PixCheckoutService, read_secret
from packages.loader import discover_packages
from persistence.accounts import AccountUser, GoogleSheetsAccountRepository
from persistence.payments import GoogleSheetsPaymentRepository
from persistence.spreadsheet_config import read_spreadsheet_ids
from persistence.v2_google_sheets import GoogleSheetsStoryCreditRepository


@dataclass(frozen=True, slots=True)
class PaymentState:
    package_id: str
    payment_order_id: str
    status: str
    approved: bool
    qr_code: str = ""
    qr_code_base64: str = ""
    ticket_url: str = ""


class PaymentGateway(Protocol):
    def master_test_available(self, *, user_id: str) -> bool: ...

    def approve_master_test(self, *, user: AccountUser, package_id: str) -> PaymentState: ...

    def create_pix(self, *, user: AccountUser, package_id: str) -> PaymentState: ...

    def refresh(self, *, user: AccountUser, payment_order_id: str) -> PaymentState: ...


class ServerPaymentGateway:
    def __init__(
        self,
        *,
        accounts: GoogleSheetsAccountRepository,
        payments: GoogleSheetsPaymentRepository,
        credits: GoogleSheetsStoryCreditRepository,
        checkout: PixCheckoutService,
        master_test: MasterTestPaymentService,
        stories_root: Path,
    ) -> None:
        self.accounts = accounts
        self.payments = payments
        self.credits = credits
        self.checkout = checkout
        self.master_test = master_test
        self.stories_root = stories_root

    def _package(self, package_id: str):
        packages, _errors = discover_packages(self.stories_root)
        package = next(
            (item for item in packages if item.manifest.package_id == package_id),
            None,
        )
        if package is None:
            raise KeyError("História não encontrada.")
        commerce = package.manifest.commerce
        if commerce.access != "paid" or commerce.price_cents <= 0:
            raise ValueError("Esta história não exige pagamento.")
        return package

    @staticmethod
    def _state(result) -> PaymentState:
        return PaymentState(
            package_id=result.stored.package_id,
            payment_order_id=result.stored.payment_order_id,
            status=result.stored.status,
            approved=bool(result.provider.approved),
            qr_code=result.provider.qr_code or result.stored.qr_code,
            qr_code_base64=result.provider.qr_code_base64,
            ticket_url=result.provider.ticket_url or result.stored.ticket_url,
        )

    def master_test_available(self, *, user_id: str) -> bool:
        return self.master_test.is_authorized(user_id=user_id)

    def approve_master_test(self, *, user: AccountUser, package_id: str) -> PaymentState:
        package = self._package(package_id)
        commerce = package.manifest.commerce
        result = self.master_test.approve_test_payment(
            user_id=user.user_id,
            package_id=package_id,
            amount_cents=commerce.price_cents,
            currency=commerce.currency,
        )
        return PaymentState(
            package_id=package_id,
            payment_order_id=result.stored.payment_order_id,
            status="approved",
            approved=True,
        )

    def create_pix(self, *, user: AccountUser, package_id: str) -> PaymentState:
        package = self._package(package_id)
        manifest = package.manifest
        commerce = manifest.commerce
        return self._state(
            self.checkout.create_checkout(
                user_id=user.user_id,
                payer_email=user.email,
                package_id=package_id,
                product_id=package_id,
                title=manifest.card.title,
                amount_cents=commerce.price_cents,
                currency=commerce.currency,
            )
        )

    def refresh(self, *, user: AccountUser, payment_order_id: str) -> PaymentState:
        stored = self.payments.find_by_payment_order_id(payment_order_id)
        if stored is None:
            raise KeyError("Cobrança não encontrada.")
        if stored.user_id != user.user_id:
            raise PermissionError("Cobrança pertence a outro usuário.")
        return self._state(self.checkout.refresh(stored))


def build_payment_gateway(
    secrets: dict[str, object],
    *,
    accounts: GoogleSheetsAccountRepository,
    stories_root: Path,
) -> ServerPaymentGateway:
    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("Google Sheets não está configurado para pagamentos.")
    access_token = read_secret(
        secrets,
        "MERCADO_PAGO_ACCESS_TOKEN",
        "MERCADOPAGO_ACCESS_TOKEN",
        "MP_ACCESS_TOKEN",
    )
    if not access_token:
        raise ValueError("Access Token do Mercado Pago não encontrado.")
    spreadsheet_id = read_spreadsheet_ids(secrets).accounts_billing
    spreadsheet = gspread.service_account_from_dict(dict(credentials)).open_by_key(
        spreadsheet_id
    )
    payments = GoogleSheetsPaymentRepository(spreadsheet)
    payments.ensure_schema()
    credits = GoogleSheetsStoryCreditRepository(spreadsheet)
    checkout = PixCheckoutService(
        client=MercadoPagoClient(access_token),
        payments=payments,
        accounts=accounts,
        story_credits=credits,
    )
    master_test = MasterTestPaymentService(
        accounts=accounts,
        payments=payments,
        story_credits=credits,
        master_emails=str(secrets.get("PAYMENT_TEST_MASTER_EMAILS", "") or ""),
    )
    return ServerPaymentGateway(
        accounts=accounts,
        payments=payments,
        credits=credits,
        checkout=checkout,
        master_test=master_test,
        stories_root=stories_root,
    )


__all__ = [
    "PaymentGateway",
    "PaymentState",
    "ServerPaymentGateway",
    "build_payment_gateway",
]
