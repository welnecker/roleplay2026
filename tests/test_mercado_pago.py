from __future__ import annotations

import hashlib
import hmac

from billing.mercado_pago import parse_pix_order, validate_webhook_signature


def test_parse_pending_pix_order() -> None:
    order = parse_pix_order(
        {
            "id": "order-123",
            "status": "action_required",
            "external_reference": "roleplay:test",
            "transactions": {
                "payments": [
                    {
                        "status": "action_required",
                        "status_detail": "waiting_transfer",
                        "payment_method": {
                            "qr_code": "000201...",
                            "qr_code_base64": "aW1hZ2U=",
                            "ticket_url": "https://example.test/pix",
                        },
                    }
                ]
            },
        }
    )

    assert order.order_id == "order-123"
    assert order.qr_code == "000201..."
    assert order.status_detail == "waiting_transfer"
    assert order.approved is False


def test_parse_approved_payment() -> None:
    order = parse_pix_order(
        {
            "id": "order-123",
            "status": "processed",
            "transactions": {"payments": [{"status": "approved", "payment_method": {}}]},
        }
    )
    assert order.approved is True


def test_validate_webhook_signature() -> None:
    secret = "segredo"
    data_id = "123456"
    request_id = "request-abc"
    timestamp = "1704908010"
    manifest = f"id:{data_id};request-id:{request_id};ts:{timestamp};"
    digest = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()

    assert validate_webhook_signature(
        x_signature=f"ts={timestamp},v1={digest}",
        x_request_id=request_id,
        data_id=data_id,
        secret=secret,
    ) is True
    assert validate_webhook_signature(
        x_signature=f"ts={timestamp},v1=invalid",
        x_request_id=request_id,
        data_id=data_id,
        secret=secret,
    ) is False
