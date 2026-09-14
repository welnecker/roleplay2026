from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

import webhook_api
from billing.mercado_pago import MercadoPagoError


class _Request:
    async def json(self):
        return {"action": "order.processed", "data": {"id": "ORD_TEST"}}


class _Payments:
    def record_webhook(self, **kwargs):
        return True


class _FailingService:
    def __init__(self, error: MercadoPagoError) -> None:
        self.error = error

    def process_provider_order(self, order_id: str):
        assert order_id == "ORD_TEST"
        raise self.error


def _call_webhook(monkeypatch, error: MercadoPagoError):
    monkeypatch.setattr(
        webhook_api,
        "build_services",
        lambda: (_FailingService(error), _Payments(), "secret"),
    )
    monkeypatch.setattr(webhook_api, "validate_webhook_signature", lambda **kwargs: True)
    return asyncio.run(
        webhook_api.mercado_pago_webhook(
            _Request(),
            data_id="ORD_TEST",
            notification_type="order",
            x_signature="valid",
            x_request_id="request-1",
        )
    )


def test_authenticated_unknown_order_is_acknowledged_without_credit(monkeypatch):
    result = _call_webhook(
        monkeypatch,
        MercadoPagoError("Order not found.", status_code=404),
    )

    assert result == {
        "received": True,
        "processed": False,
        "ignored": True,
        "reason": "provider_order_not_found",
    }


def test_provider_outage_remains_retryable(monkeypatch):
    with pytest.raises(HTTPException) as raised:
        _call_webhook(
            monkeypatch,
            MercadoPagoError("Provider unavailable.", status_code=503),
        )

    assert raised.value.status_code == 502
