from __future__ import annotations

from typing import Any

from persistence.accounts import GoogleSheetsAccountRepository


class FakeWorksheet:
    def __init__(self, title: str) -> None:
        self.title = title
        self.rows: list[list[Any]] = []

    def row_values(self, index: int) -> list[Any]:
        if index < 1 or index > len(self.rows):
            return []
        return list(self.rows[index - 1])

    def append_row(self, values: list[Any], value_input_option: str = "RAW") -> None:
        self.rows.append(list(values))

    def get_all_records(self, default_blank: str = "") -> list[dict[str, Any]]:
        if not self.rows:
            return []
        headers = [str(value) for value in self.rows[0]]
        return [
            {
                header: row[index] if index < len(row) else default_blank
                for index, header in enumerate(headers)
            }
            for row in self.rows[1:]
        ]


class FakeSpreadsheet:
    def __init__(self) -> None:
        self.sheets: dict[str, FakeWorksheet] = {}

    def worksheet(self, name: str) -> FakeWorksheet:
        import gspread

        if name not in self.sheets:
            raise gspread.WorksheetNotFound(name)
        return self.sheets[name]

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        worksheet = FakeWorksheet(title)
        self.sheets[title] = worksheet
        return worksheet


def build_repository() -> GoogleSheetsAccountRepository:
    repository = GoogleSheetsAccountRepository(FakeSpreadsheet())  # type: ignore[arg-type]
    repository.ensure_schema()
    return repository


def test_register_and_authenticate_user() -> None:
    repository = build_repository()

    created = repository.register(
        email="pessoa@example.com",
        password="senha-segura",
        display_name="Pessoa",
    )

    authenticated = repository.authenticate(
        email="PESSOA@example.com",
        password="senha-segura",
    )

    assert authenticated is not None
    assert authenticated.user_id == created.user_id
    assert authenticated.email == "pessoa@example.com"
    assert repository.authenticate(email="pessoa@example.com", password="incorreta") is None


def test_duplicate_email_is_rejected() -> None:
    repository = build_repository()
    repository.register(
        email="pessoa@example.com",
        password="senha-segura",
        display_name="Pessoa",
    )

    try:
        repository.register(
            email="PESSOA@example.com",
            password="outra-senha",
            display_name="Outra pessoa",
        )
    except ValueError as exc:
        assert "Já existe" in str(exc)
    else:
        raise AssertionError("Cadastro duplicado deveria ser rejeitado")


def test_paid_access_requires_active_entitlement() -> None:
    repository = build_repository()
    user = repository.register(
        email="pessoa@example.com",
        password="senha-segura",
        display_name="Pessoa",
    )

    assert repository.has_entitlement(
        user_id=user.user_id,
        package_id="example.paid",
        access="paid",
    ) is False

    first_id = repository.grant_entitlement(
        user_id=user.user_id,
        package_id="example.paid",
        product_id="example-product",
        source="test",
        payment_id="payment-1",
    )
    second_id = repository.grant_entitlement(
        user_id=user.user_id,
        package_id="example.paid",
        product_id="example-product",
        source="test",
        payment_id="payment-1",
    )

    assert first_id == second_id
    assert repository.has_entitlement(
        user_id=user.user_id,
        package_id="example.paid",
        access="paid",
    ) is True
    assert repository.has_entitlement(
        user_id=user.user_id,
        package_id="example.free",
        access="free",
    ) is True
