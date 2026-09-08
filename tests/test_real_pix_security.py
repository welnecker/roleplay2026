from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from billing.master_test import MasterTestPaymentService
from billing.mercado_pago import PixOrder
from billing.service import PaymentValidationError, validate_approved_order
from persistence.payments import GoogleSheetsPaymentRepository, StoredPaymentOrder


def stored_order(**changes: object) -> StoredPaymentOrder:
    base = StoredPaymentOrder(
        payment_order_id="payord_1",
        user_id="user_1",
        package_id="roleplay2026.camilly",
        product_id="roleplay2026.camilly",
        amount_cents=990,
        currency="BRL",
        payer_email_normalized="cliente@example.com",
        payment_mode="real_pix",
        provider="mercado_pago",
        provider_order_id="mp_1",
        external_reference="rp26_1",
        idempotency_key="idem_1",
        status="approved",
        status_detail="accredited",
        qr_code="",
        ticket_url="",
        validation_status="valid",
        approved_at="2026-08-20T00:00:00+00:00",
    )
    return replace(base, **changes)


def provider_order(**changes: object) -> PixOrder:
    base = PixOrder(
        order_id="mp_1",
        status="approved",
        status_detail="accredited",
        external_reference="rp26_1",
        qr_code="",
        qr_code_base64="",
        ticket_url="",
        amount_cents=990,
        currency="BRL",
        raw={},
    )
    return replace(base, **changes)


@pytest.mark.parametrize(
    ("provider_changes", "stored_changes", "message"),
    [
        ({"status": "action_required"}, {}, "ainda não foi aprovado"),
        ({"status": "rejected"}, {}, "ainda não foi aprovado"),
        ({"status": "cancelled"}, {}, "ainda não foi aprovado"),
        ({"status": "expired"}, {}, "ainda não foi aprovado"),
        ({"order_id": "mp_other"}, {}, "Identificador externo"),
        ({"external_reference": "rp26_other"}, {}, "Referência externa"),
        ({"amount_cents": 100}, {}, "Valor aprovado"),
        ({"currency": "USD"}, {}, "Moeda aprovada"),
        ({}, {"product_id": "roleplay2026.other"}, "Produto e pacote"),
    ],
)
def test_invalid_or_pending_payment_never_validates(
    provider_changes: dict[str, object],
    stored_changes: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(PaymentValidationError, match=message):
        validate_approved_order(
            stored_order(**stored_changes), provider_order(**provider_changes)
        )


def test_approved_matching_payment_validates() -> None:
    validate_approved_order(stored_order(), provider_order())


class FakeAccounts:
    def __init__(self, email: str) -> None:
        self.email = email

    def get_user(self, *, user_id: str) -> object | None:
        if user_id != "user_1":
            return None
        return SimpleNamespace(
            user_id="user_1", email=self.email, display_name="Master", status="active"
        )


class FakePayments:
    def __init__(self) -> None:
        self.created: dict[str, object] | None = None
        self.updated: dict[str, object] | None = None

    def create_pending_order(self, **values: object) -> StoredPaymentOrder:
        self.created = values
        return stored_order(
            payer_email_normalized=str(values["payer_email_normalized"]),
            payment_mode=str(values["payment_mode"]),
            provider=str(values["provider"]),
            provider_order_id="",
            external_reference=str(values["external_reference"]),
            status="creating",
            validation_status="pending",
            approved_at="",
        )

    def update_provider_order(self, **values: object) -> StoredPaymentOrder:
        self.updated = values
        return stored_order(
            payer_email_normalized="welnecker@hotmail.com",
            payment_mode="test_master",
            provider="test_master",
            provider_order_id=str(values["provider_order_id"]),
            external_reference=str(self.created["external_reference"]),
            status="approved",
            validation_status="valid",
        )


class FakeCredits:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def create_credit(self, **values: str) -> object:
        self.calls.append(values)
        return object()


def test_master_test_uses_persisted_identity_and_is_audited() -> None:
    payments = FakePayments()
    credits = FakeCredits()
    service = MasterTestPaymentService(
        accounts=FakeAccounts("  WELNECKER@HOTMAIL.COM "),  # type: ignore[arg-type]
        payments=payments,  # type: ignore[arg-type]
        story_credits=credits,
        master_emails="welnecker@hotmail.com",
    )

    result = service.approve_test_payment(
        user_id="user_1",
        package_id="roleplay2026.camilly",
        amount_cents=990,
        currency="BRL",
    )

    assert payments.created is not None
    assert payments.created["payment_mode"] == "test_master"
    assert payments.created["provider"] == "test_master"
    assert payments.created["payer_email_normalized"] == "welnecker@hotmail.com"
    assert payments.updated is not None
    assert payments.updated["validation_status"] == "valid"
    assert credits.calls == [
        {
            "user_id": "user_1",
            "package_id": "roleplay2026.camilly",
            "payment_id": result.payment_id,
        }
    ]


def test_email_parameter_cannot_turn_common_user_into_master() -> None:
    service = MasterTestPaymentService(
        accounts=FakeAccounts("cliente@example.com"),  # type: ignore[arg-type]
        payments=FakePayments(),  # type: ignore[arg-type]
        story_credits=FakeCredits(),
        master_emails="welnecker@hotmail.com",
    )

    assert service.is_authorized(user_id="user_1") is False
    with pytest.raises(PermissionError):
        service.approve_test_payment(
            user_id="user_1",
            package_id="roleplay2026.camilly",
            amount_cents=990,
            currency="BRL",
        )


class FakeWebhookWorksheet:
    def __init__(self) -> None:
        self.headers = [
            "webhook_event_id",
            "provider_event_id",
            "provider_order_id",
            "event_type",
            "signature_valid",
            "payload_json",
            "created_at",
        ]
        self.rows: list[list[object]] = []

    def row_values(self, row_number: int) -> list[object]:
        return self.headers if row_number == 1 else []

    def get_all_records(self, default_blank: str = "") -> list[dict[str, object]]:
        return [dict(zip(self.headers, row, strict=False)) for row in self.rows]

    def append_row(self, values: list[object], value_input_option: str = "RAW") -> None:
        self.rows.append(values)


class FakeWebhookSpreadsheet:
    def __init__(self) -> None:
        self.sheet = FakeWebhookWorksheet()

    def worksheet(self, name: str) -> FakeWebhookWorksheet:
        assert name == "WEBHOOK_EVENTS"
        return self.sheet


def test_repeated_webhook_event_is_idempotent() -> None:
    repository = GoogleSheetsPaymentRepository(FakeWebhookSpreadsheet())  # type: ignore[arg-type]

    first = repository.record_webhook(
        provider_event_id="event_1",
        provider_order_id="mp_1",
        event_type="order.updated",
        signature_valid=True,
        payload={"id": "event_1"},
    )
    repeated = repository.record_webhook(
        provider_event_id="event_1",
        provider_order_id="mp_1",
        event_type="order.updated",
        signature_valid=True,
        payload={"id": "event_1"},
    )

    assert first is True
    assert repeated is False
    assert len(repository.spreadsheet.sheet.rows) == 1  # type: ignore[attr-defined]
