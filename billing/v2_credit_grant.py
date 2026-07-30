from __future__ import annotations

from typing import Protocol


class StoryCreditGrantRepository(Protocol):
    """Contrato mínimo usado pelo billing para registrar um crédito narrativo."""

    def create_credit(
        self,
        *,
        user_id: str,
        package_id: str,
        payment_id: str,
    ) -> object: ...
