from __future__ import annotations

from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from psycopg.errors import UniqueViolation

from persistence.accounts import AccountUser
from persistence.models import new_id
from persistence.postgres_database import PostgresDatabase


class PostgresAccountRepository:
    """Contas transacionais compartilhadas por todas as instâncias do backend."""

    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database
        self.hasher = PasswordHasher()

    def ensure_schema(self) -> None:
        self.database.ensure_schema()

    def register(self, *, email: str, password: str, display_name: str) -> AccountUser:
        clean_email = email.strip().casefold()
        clean_name = display_name.strip()
        if "@" not in clean_email:
            raise ValueError("E-mail inválido.")
        if len(password) < 8:
            raise ValueError("A senha deve ter ao menos 8 caracteres.")
        if not clean_name:
            raise ValueError("Nome de exibição obrigatório.")

        user_id = new_id("user")
        credential_id = new_id("cred")
        password_hash = self.hasher.hash(password)
        try:
            with self.database.pool.connection() as connection:
                with connection.transaction():
                    connection.execute(
                        """
                        INSERT INTO users(
                            user_id, email, display_name, status
                        ) VALUES (%s, %s, %s, 'active')
                        """,
                        (user_id, clean_email, clean_name),
                    )
                    connection.execute(
                        """
                        INSERT INTO user_credentials(
                            credential_id, user_id, password_hash, status
                        ) VALUES (%s, %s, %s, 'active')
                        """,
                        (credential_id, user_id, password_hash),
                    )
        except UniqueViolation as exc:
            raise ValueError("Já existe uma conta com este e-mail.") from exc

        return AccountUser(
            user_id=user_id,
            email=clean_email,
            display_name=clean_name,
            status="active",
        )

    def authenticate(self, *, email: str, password: str) -> AccountUser | None:
        clean_email = email.strip().casefold()
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT u.user_id, u.email, u.display_name, u.status, c.password_hash
                FROM users AS u
                JOIN user_credentials AS c ON c.user_id = u.user_id
                WHERE u.email = %s
                  AND u.status = 'active'
                  AND c.status = 'active'
                LIMIT 1
                """,
                (clean_email,),
            ).fetchone()
        if row is None:
            return None
        try:
            if not self.hasher.verify(str(row[4]), password):
                return None
        except (VerifyMismatchError, InvalidHashError):
            return None
        return AccountUser(
            user_id=str(row[0]),
            email=str(row[1]),
            display_name=str(row[2]),
            status=str(row[3]),
        )

    def get_user(self, *, user_id: str) -> AccountUser | None:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT user_id, email, display_name, status
                FROM users
                WHERE user_id = %s
                LIMIT 1
                """,
                (user_id.strip(),),
            ).fetchone()
        if row is None:
            return None
        return AccountUser(
            user_id=str(row[0]),
            email=str(row[1]),
            display_name=str(row[2]),
            status=str(row[3]),
        )

    def has_entitlement(self, *, user_id: str, package_id: str, access: str) -> bool:
        if access == "free":
            return True
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                SELECT 1
                FROM user_entitlements
                WHERE user_id = %s
                  AND package_id = %s
                  AND status = 'active'
                LIMIT 1
                """,
                (user_id, package_id),
            ).fetchone()
        return row is not None

    def grant_entitlement(
        self,
        *,
        user_id: str,
        package_id: str,
        product_id: str,
        source: str,
        payment_id: str = "",
    ) -> str:
        entitlement_id = new_id("ent")
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO user_entitlements(
                    entitlement_id, user_id, package_id, product_id,
                    status, source, payment_id
                )
                VALUES (%s, %s, %s, %s, 'active', %s, %s)
                ON CONFLICT (user_id, package_id) WHERE status = 'active'
                DO UPDATE SET
                    product_id = EXCLUDED.product_id,
                    source = EXCLUDED.source,
                    payment_id = EXCLUDED.payment_id,
                    updated_at = now()
                RETURNING entitlement_id
                """,
                (
                    entitlement_id,
                    user_id,
                    package_id,
                    product_id,
                    source,
                    payment_id,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Não foi possível registrar o acesso da história.")
        return str(row[0])


__all__ = ["PostgresAccountRepository"]
