from __future__ import annotations

from typing import Protocol

from platform_core.auth import AuthenticatedUser
from platform_core.models import StoryCard


class UserRepository(Protocol):
    def authenticate(self, email: str, password: str) -> AuthenticatedUser | None: ...


class StoryRepository(Protocol):
    def list_for_user(self, user_id: str) -> list[StoryCard]: ...


class SaveRepository(Protocol):
    def start(self, user_id: str, package_id: str) -> None: ...
    def restart(self, user_id: str, package_id: str) -> None: ...
    def restore(self, user_id: str, package_id: str) -> dict[str, object] | None: ...


class InteractionRepository(Protocol):
    def append(self, interaction: dict[str, object]) -> None: ...
    def list_recent(self, save_id: str, limit: int = 30) -> list[dict[str, object]]: ...


class PaymentRepository(Protocol):
    def create_pix_checkout(self, user_id: str, package_id: str) -> dict[str, str]: ...
