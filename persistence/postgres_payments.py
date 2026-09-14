from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from persistence.models import new_id
from persistence.payments import StoredPaymentOrder
from persistence.postgres_database import PostgresDatabase


_COLUMNS = """payment_order_id, user_id, package_id, product_id, amount_cents,
currency, payer_email_normalized, payment_mode, provider, provider_order_id,
external_reference, idempotency_key, status, status_detail, qr_code, ticket_url,
validation_status, approved_at"""


def _iso(value: object) -> str:
    return value.isoformat() if isinstance(value, datetime) else str(value or "")


def _order(row: tuple[Any, ...]) -> StoredPaymentOrder:
    return StoredPaymentOrder(
        payment_order_id=str(row[0]), user_id=str(row[1]),
        package_id=str(row[2]), product_id=str(row[3]), amount_cents=int(row[4]),
        currency=str(row[5]), payer_email_normalized=str(row[6]),
        payment_mode=str(row[7]), provider=str(row[8]),
        provider_order_id=str(row[9] or ""), external_reference=str(row[10]),
        idempotency_key=str(row[11]), status=str(row[12]),
        status_detail=str(row[13] or ""), qr_code=str(row[14] or ""),
        ticket_url=str(row[15] or ""), validation_status=str(row[16]),
        approved_at=_iso(row[17]),
    )


class PostgresPaymentRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database

    def ensure_schema(self) -> None:
        self.database.ensure_schema()

    def create_pending_order(self, **values: Any) -> StoredPaymentOrder:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"""INSERT INTO payment_orders(
                    payment_order_id, user_id, package_id, product_id,
                    amount_cents, currency, payer_email_normalized, payment_mode,
                    provider, external_reference, idempotency_key, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'creating')
                ON CONFLICT (external_reference)
                DO UPDATE SET external_reference = EXCLUDED.external_reference
                RETURNING {_COLUMNS}""",
                (
                    new_id("payord"), str(values["user_id"]),
                    str(values["package_id"]), str(values["product_id"]),
                    int(values["amount_cents"]), str(values["currency"]),
                    str(values.get("payer_email_normalized", "")).strip().casefold(),
                    str(values.get("payment_mode", "real_pix")),
                    str(values.get("provider", "mercado_pago")),
                    str(values["external_reference"]), str(values["idempotency_key"]),
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Não foi possível criar a ordem.")
        result = _order(row)
        if result.user_id != str(values["user_id"]):
            raise RuntimeError("Referência de pagamento pertence a outro usuário.")
        return result

    def update_provider_order(
        self, *, payment_order_id: str, provider_order_id: str,
        status: str, status_detail: str, qr_code: str, ticket_url: str,
        raw: dict[str, Any], validation_status: str = "pending",
        approved_at: str = "",
    ) -> StoredPaymentOrder:
        with self.database.pool.connection() as connection:
            with connection.transaction():
                row = connection.execute(
                    f"""UPDATE payment_orders SET
                        provider_order_id=%s, status=%s, status_detail=%s,
                        qr_code=%s, ticket_url=%s, validation_status=%s,
                        approved_at=%s, updated_at=now()
                        WHERE payment_order_id=%s RETURNING {_COLUMNS}""",
                    (
                        provider_order_id, status, status_detail, qr_code,
                        ticket_url, validation_status, approved_at or None,
                        payment_order_id,
                    ),
                ).fetchone()
                if row is None:
                    raise KeyError(f"Pagamento não encontrado: {payment_order_id}")
                connection.execute(
                    """INSERT INTO payment_events(
                        payment_event_id, payment_order_id, provider_order_id,
                        event_type, status, payload_json
                    ) VALUES (%s,%s,%s,'provider_order_updated',%s,%s::jsonb)""",
                    (
                        new_id("payeve"), payment_order_id, provider_order_id,
                        status, json.dumps(raw, ensure_ascii=False),
                    ),
                )
        return _order(row)

    def _find(self, column: str, value: str) -> StoredPaymentOrder | None:
        allowed = {
            "external_reference", "payment_order_id", "provider_order_id"
        }
        if column not in allowed:
            raise ValueError("Coluna de pagamento inválida.")
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"SELECT {_COLUMNS} FROM payment_orders WHERE {column} = %s",
                (value,),
            ).fetchone()
        return _order(row) if row is not None else None

    def find_by_external_reference(self, value: str) -> StoredPaymentOrder | None:
        return self._find("external_reference", value)

    def find_by_payment_order_id(self, value: str) -> StoredPaymentOrder | None:
        return self._find("payment_order_id", value)

    def find_by_provider_order_id(self, value: str) -> StoredPaymentOrder | None:
        return self._find("provider_order_id", value)

    def append_payment_event(
        self, *, payment_order_id: str, provider_order_id: str,
        event_type: str, status: str, payload: dict[str, Any],
    ) -> str:
        event_id = new_id("payeve")
        with self.database.pool.connection() as connection:
            connection.execute(
                """INSERT INTO payment_events(
                    payment_event_id, payment_order_id, provider_order_id,
                    event_type, status, payload_json
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
                (
                    event_id, payment_order_id, provider_order_id, event_type,
                    status, json.dumps(payload, ensure_ascii=False),
                ),
            )
        return event_id

    def record_webhook(
        self, *, provider_event_id: str, provider_order_id: str,
        event_type: str, signature_valid: bool, payload: dict[str, Any],
    ) -> bool:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """INSERT INTO webhook_events(
                    webhook_event_id, provider_event_id, provider_order_id,
                    event_type, signature_valid, payload_json
                ) VALUES (%s,%s,%s,%s,%s,%s::jsonb)
                ON CONFLICT (provider_event_id) WHERE provider_event_id <> ''
                DO NOTHING RETURNING webhook_event_id""",
                (
                    new_id("wh"), provider_event_id, provider_order_id,
                    event_type, signature_valid,
                    json.dumps(payload, ensure_ascii=False),
                ),
            ).fetchone()
        return row is not None


__all__ = ["PostgresPaymentRepository"]
