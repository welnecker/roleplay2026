from __future__ import annotations

from types import SimpleNamespace

from billing.mercado_pago import PixOrder
from billing.service import PixCheckoutService


class FakeAccounts:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def grant_entitlement(self, **kwargs: str) -> None:
        self.calls.append(dict(kwargs))


class FakeCredits:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def create_credit(self, **kwargs: str) -> object:
        self.calls.append(dict(kwargs))
        return object()


def approved_provider() -> PixOrder:
    return PixOrder(
        order_id="mp_123",
        status="approved",
        status_detail="accredited",
        external_reference="rp26_test",
        qr_code="",
        qr_code_base64="",
        ticket_url="",
        raw={},
    )


def stored_order() -> SimpleNamespace:
    return SimpleNamespace(
        user_id="user_1",
        package_id="casada_frustrada",
        product_id="casada_frustrada",
    )


def test_approved_payment_grants_only_v2_credit_when_configured() -> None:
    accounts = FakeAccounts()
    credits = FakeCredits()
    service = PixCheckoutService(
        client=SimpleNamespace(),
        payments=SimpleNamespace(),
        accounts=accounts,  # type: ignore[arg-type]
        story_credits=credits,
    )

    service._grant(stored_order(), approved_provider())  # type: ignore[arg-type]

    assert accounts.calls == []
    assert credits.calls == [
        {
            "user_id": "user_1",
            "package_id": "casada_frustrada",
            "payment_id": "mp_123",
        }
    ]


def test_approved_payment_uses_legacy_entitlement_without_v2_credit_repository() -> None:
    accounts = FakeAccounts()
    service = PixCheckoutService(
        client=SimpleNamespace(),
        payments=SimpleNamespace(),
        accounts=accounts,  # type: ignore[arg-type]
        story_credits=None,
    )

    service._grant(stored_order(), approved_provider())  # type: ignore[arg-type]

    assert accounts.calls == [
        {
            "user_id": "user_1",
            "package_id": "casada_frustrada",
            "product_id": "casada_frustrada",
            "source": "mercado_pago_pix",
            "payment_id": "mp_123",
        }
    ]
