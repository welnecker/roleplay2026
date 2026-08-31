from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: str
    email: str
    display_name: str


def demo_auth_allowed(secrets: Any) -> bool:
    """Permite login demonstrativo apenas quando não há infraestrutura real configurada."""

    return not bool(secrets.get("gcp_service_account"))


def authenticate_demo(email: str, password: str) -> AuthenticatedUser | None:
    clean_email = email.strip().lower()
    if not clean_email or "@" not in clean_email or not password:
        return None

    display_name = clean_email.split("@", maxsplit=1)[0].replace(".", " ").title()
    return AuthenticatedUser(
        user_id=f"demo:{clean_email}",
        email=clean_email,
        display_name=display_name,
    )
