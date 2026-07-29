from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

import gspread
from gspread import Spreadsheet, Worksheet

from persistence.models import new_id, utc_now_iso

PAYMENT_ORDERS_SHEET = "PAYMENT_ORDERS"
PAYMENT_EVENTS_SHEET = "PAYMENT_EVENTS"
WEBHOOK_EVENTS_SHEET = "WEBHOOK_EVENTS"

PAYMENT_ORDERS_HEADERS = (
    "payment_order_id", "user_id", "package_id", "product_id", "amount_cents",
    "currency", "provider", "provider_order_id", "external_reference",
    "idempotency_key", "status", "status_detail", "qr_code", "ticket_url",
    "created_at", "updated_at",
)
PAYMENT_EVENTS_HEADERS = (
    "payment_event_id", "payment_order_id", "provider_order_id", "event_type",
    "status", "payload_json", "created_at",
)
WEBHOOK_EVENTS_HEADERS = (
    "webhook_event_id", "provider_event_id", "provider_order_id", "event_type",
    "signature_valid", "payload_json", "created_at",
)


@dataclass(frozen=True, slots=True)
class StoredPaymentOrder:
    payment_order_id: str
    user_id: str
    package_id: str
    product_id: str
    amount_cents: int
    currency: str
    provider_order_id: str
    external_reference: str
    idempotency_key: str
    status: str
    status_detail: str
    qr_code: str
    ticket_url: str


class GoogleSheetsPaymentRepository:
    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.spreadsheet = spreadsheet
        self._worksheets: dict[str, Worksheet] = {}

    def ensure_schema(self) -> None:
        self._ensure_sheet(PAYMENT_ORDERS_SHEET, PAYMENT_ORDERS_HEADERS)
        self._ensure_sheet(PAYMENT_EVENTS_SHEET, PAYMENT_EVENTS_HEADERS)
        self._ensure_sheet(WEBHOOK_EVENTS_SHEET, WEBHOOK_EVENTS_HEADERS)

    def create_pending_order(self, **values: Any) -> StoredPaymentOrder:
        existing = self.find_by_external_reference(str(values["external_reference"]))
        if existing is not None:
            return existing
        now = utc_now_iso()
        order = StoredPaymentOrder(
            payment_order_id=new_id("payord"),
            user_id=str(values["user_id"]),
            package_id=str(values["package_id"]),
            product_id=str(values["product_id"]),
            amount_cents=int(values["amount_cents"]),
            currency=str(values["currency"]),
            provider_order_id="",
            external_reference=str(values["external_reference"]),
            idempotency_key=str(values["idempotency_key"]),
            status="creating",
            status_detail="",
            qr_code="",
            ticket_url="",
        )
        self._append(self._worksheet(PAYMENT_ORDERS_SHEET), {
            **asdict(order), "provider": "mercado_pago", "created_at": now, "updated_at": now,
        })
        return order

    def update_provider_order(self, *, payment_order_id: str, provider_order_id: str,
                              status: str, status_detail: str, qr_code: str,
                              ticket_url: str, raw: dict[str, Any]) -> StoredPaymentOrder:
        row_number, row = self._find_row("payment_order_id", payment_order_id)
        row.update({
            "provider_order_id": provider_order_id,
            "status": status,
            "status_detail": status_detail,
            "qr_code": qr_code,
            "ticket_url": ticket_url,
            "updated_at": utc_now_iso(),
        })
        self._update_row(self._worksheet(PAYMENT_ORDERS_SHEET), row_number, row)
        self.append_payment_event(
            payment_order_id=payment_order_id,
            provider_order_id=provider_order_id,
            event_type="provider_order_updated",
            status=status,
            payload=raw,
        )
        return self._to_order(row)

    def find_by_external_reference(self, external_reference: str) -> StoredPaymentOrder | None:
        return self._find("external_reference", external_reference)

    def find_by_provider_order_id(self, provider_order_id: str) -> StoredPaymentOrder | None:
        return self._find("provider_order_id", provider_order_id)

    def append_payment_event(self, *, payment_order_id: str, provider_order_id: str,
                             event_type: str, status: str, payload: dict[str, Any]) -> str:
        event_id = new_id("payeve")
        self._append(self._worksheet(PAYMENT_EVENTS_SHEET), {
            "payment_event_id": event_id,
            "payment_order_id": payment_order_id,
            "provider_order_id": provider_order_id,
            "event_type": event_type,
            "status": status,
            "payload_json": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "created_at": utc_now_iso(),
        })
        return event_id

    def record_webhook(self, *, provider_event_id: str, provider_order_id: str,
                       event_type: str, signature_valid: bool,
                       payload: dict[str, Any]) -> bool:
        if provider_event_id and self._find_record(WEBHOOK_EVENTS_SHEET, "provider_event_id", provider_event_id):
            return False
        self._append(self._worksheet(WEBHOOK_EVENTS_SHEET), {
            "webhook_event_id": new_id("wh"),
            "provider_event_id": provider_event_id,
            "provider_order_id": provider_order_id,
            "event_type": event_type,
            "signature_valid": "true" if signature_valid else "false",
            "payload_json": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "created_at": utc_now_iso(),
        })
        return True

    def _find(self, key: str, value: str) -> StoredPaymentOrder | None:
        row = self._find_record(PAYMENT_ORDERS_SHEET, key, value)
        return self._to_order(row) if row else None

    def _find_record(self, sheet: str, key: str, value: str) -> dict[str, Any] | None:
        for row in self._records(sheet):
            if str(row.get(key, "")) == value:
                return row
        return None

    def _find_row(self, key: str, value: str) -> tuple[int, dict[str, Any]]:
        for number, row in enumerate(self._worksheet(PAYMENT_ORDERS_SHEET).get_all_records(default_blank=""), start=2):
            if str(row.get(key, "")) == value:
                return number, dict(row)
        raise KeyError(f"Pagamento não encontrado: {value}")

    def _ensure_sheet(self, name: str, headers: tuple[str, ...]) -> None:
        try:
            worksheet = self._worksheet(name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
            self._worksheets[name] = worksheet
        current = tuple(str(value).strip() for value in worksheet.row_values(1))
        if not current:
            worksheet.append_row(list(headers), value_input_option="RAW")
        elif current != headers:
            raise RuntimeError(f"Cabeçalhos incompatíveis na aba {name}.")

    def _worksheet(self, name: str) -> Worksheet:
        if name not in self._worksheets:
            self._worksheets[name] = self.spreadsheet.worksheet(name)
        return self._worksheets[name]

    def _records(self, name: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self._worksheet(name).get_all_records(default_blank="")]

    @staticmethod
    def _append(worksheet: Worksheet, data: dict[str, Any]) -> None:
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        worksheet.append_row([data.get(header, "") for header in headers], value_input_option="RAW")

    @staticmethod
    def _update_row(worksheet: Worksheet, row_number: int, data: dict[str, Any]) -> None:
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        end = gspread.utils.rowcol_to_a1(row_number, len(headers))
        worksheet.update(f"A{row_number}:{end}", [[data.get(h, "") for h in headers]], value_input_option="RAW")

    @staticmethod
    def _to_order(row: dict[str, Any]) -> StoredPaymentOrder:
        return StoredPaymentOrder(
            payment_order_id=str(row.get("payment_order_id", "")),
            user_id=str(row.get("user_id", "")),
            package_id=str(row.get("package_id", "")),
            product_id=str(row.get("product_id", "")),
            amount_cents=int(row.get("amount_cents", 0) or 0),
            currency=str(row.get("currency", "BRL")),
            provider_order_id=str(row.get("provider_order_id", "")),
            external_reference=str(row.get("external_reference", "")),
            idempotency_key=str(row.get("idempotency_key", "")),
            status=str(row.get("status", "")),
            status_detail=str(row.get("status_detail", "")),
            qr_code=str(row.get("qr_code", "")),
            ticket_url=str(row.get("ticket_url", "")),
        )
