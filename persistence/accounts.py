from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, ClassVar

import gspread
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from gspread import Spreadsheet, Worksheet

from persistence.models import new_id, utc_now_iso

USERS_SHEET = "USERS"
CREDENTIALS_SHEET = "USER_CREDENTIALS"
ENTITLEMENTS_SHEET = "USER_ENTITLEMENTS"
RECORDS_CACHE_TTL_SECONDS = 30.0

USERS_HEADERS = (
    "user_id",
    "email",
    "display_name",
    "status",
    "created_at",
    "updated_at",
)
CREDENTIALS_HEADERS = (
    "credential_id",
    "user_id",
    "password_hash",
    "status",
    "created_at",
    "updated_at",
)
ENTITLEMENTS_HEADERS = (
    "entitlement_id",
    "user_id",
    "package_id",
    "product_id",
    "status",
    "source",
    "payment_id",
    "created_at",
    "updated_at",
)

PaidAccessResolver = Callable[..., bool]


@dataclass(frozen=True, slots=True)
class AccountUser:
    user_id: str
    email: str
    display_name: str
    status: str


class GoogleSheetsAccountRepository:
    _paid_access_resolver: ClassVar[PaidAccessResolver | None] = None

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.spreadsheet = spreadsheet
        self.hasher = PasswordHasher()
        self._worksheets: dict[str, Worksheet] = {}
        self._records_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    @classmethod
    def configure_paid_access_resolver(cls, resolver: PaidAccessResolver | None) -> None:
        cls._paid_access_resolver = resolver

    def ensure_schema(self) -> None:
        self._ensure_sheet(USERS_SHEET, USERS_HEADERS)
        self._ensure_sheet(CREDENTIALS_SHEET, CREDENTIALS_HEADERS)
        self._ensure_sheet(ENTITLEMENTS_SHEET, ENTITLEMENTS_HEADERS)

    def register(self, *, email: str, password: str, display_name: str) -> AccountUser:
        clean_email = email.strip().lower()
        clean_name = display_name.strip()
        if "@" not in clean_email:
            raise ValueError("E-mail inválido.")
        if len(password) < 8:
            raise ValueError("A senha deve ter ao menos 8 caracteres.")
        if not clean_name:
            raise ValueError("Nome de exibição obrigatório.")
        if self._find_user_by_email(clean_email) is not None:
            raise ValueError("Já existe uma conta com este e-mail.")

        now = utc_now_iso()
        user = AccountUser(
            user_id=new_id("user"),
            email=clean_email,
            display_name=clean_name,
            status="active",
        )
        self._append(
            USERS_SHEET,
            {
                "user_id": user.user_id,
                "email": user.email,
                "display_name": user.display_name,
                "status": user.status,
                "created_at": now,
                "updated_at": now,
            },
        )
        self._append(
            CREDENTIALS_SHEET,
            {
                "credential_id": new_id("cred"),
                "user_id": user.user_id,
                "password_hash": self.hasher.hash(password),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        )
        return user

    def authenticate(self, *, email: str, password: str) -> AccountUser | None:
        found = self._find_user_by_email(email.strip().lower())
        if found is None:
            return None
        user_row = found[1]
        if str(user_row.get("status", "")) != "active":
            return None

        credential = self._find_credential(str(user_row["user_id"]))
        if credential is None or str(credential.get("status", "")) != "active":
            return None
        try:
            if not self.hasher.verify(str(credential.get("password_hash", "")), password):
                return None
        except (VerifyMismatchError, InvalidHashError):
            return None

        return AccountUser(
            user_id=str(user_row["user_id"]),
            email=str(user_row["email"]),
            display_name=str(user_row["display_name"]),
            status=str(user_row["status"]),
        )

    def has_entitlement(self, *, user_id: str, package_id: str, access: str) -> bool:
        if access == "free":
            return True
        resolver = type(self)._paid_access_resolver
        if resolver is not None:
            return bool(
                resolver(
                    user_id=user_id,
                    package_id=package_id,
                    access=access,
                )
            )
        return any(
            str(row.get("user_id", "")) == user_id
            and str(row.get("package_id", "")) == package_id
            and str(row.get("status", "")) == "active"
            for row in self._records(ENTITLEMENTS_SHEET)
        )

    def grant_entitlement(
        self,
        *,
        user_id: str,
        package_id: str,
        product_id: str,
        source: str,
        payment_id: str = "",
    ) -> str:
        for row in self._records(ENTITLEMENTS_SHEET):
            if (
                str(row.get("user_id", "")) == user_id
                and str(row.get("package_id", "")) == package_id
                and str(row.get("status", "")) == "active"
            ):
                return str(row["entitlement_id"])
        now = utc_now_iso()
        entitlement_id = new_id("ent")
        self._append(
            ENTITLEMENTS_SHEET,
            {
                "entitlement_id": entitlement_id,
                "user_id": user_id,
                "package_id": package_id,
                "product_id": product_id,
                "status": "active",
                "source": source,
                "payment_id": payment_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        return entitlement_id

    def _find_user_by_email(self, email: str) -> tuple[int, dict[str, Any]] | None:
        for row_number, row in enumerate(self._records(USERS_SHEET), start=2):
            if str(row.get("email", "")).strip().lower() == email:
                return row_number, dict(row)
        return None

    def _find_credential(self, user_id: str) -> dict[str, Any] | None:
        for row in self._records(CREDENTIALS_SHEET):
            if str(row.get("user_id", "")) == user_id:
                return row
        return None

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
        now = monotonic()
        cached = self._records_cache.get(name)
        if cached is not None:
            expires_at, rows = cached
            if now < expires_at:
                return [dict(row) for row in rows]

        rows = [dict(row) for row in self._worksheet(name).get_all_records(default_blank="")]
        self._records_cache[name] = (now + RECORDS_CACHE_TTL_SECONDS, rows)
        return [dict(row) for row in rows]

    def _append(self, sheet_name: str, data: dict[str, Any]) -> None:
        worksheet = self._worksheet(sheet_name)
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        worksheet.append_row([data.get(header, "") for header in headers], value_input_option="RAW")
        self._records_cache.pop(sheet_name, None)
