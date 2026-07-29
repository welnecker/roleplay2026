from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: str
    email: str
    display_name: str


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
