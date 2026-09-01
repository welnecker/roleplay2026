from __future__ import annotations

from typing import Any

import flet_secure_storage as fss


AUTH_TOKEN_KEY = "br.com.entrecenas.roleplay.api_session"


class AuthTokenStorage:
    """Armazena somente o bearer token no cofre nativo da plataforma."""

    def __init__(self, storage: Any | None = None) -> None:
        self._storage = storage or fss.SecureStorage()

    async def get_token(self) -> str:
        value = await self._storage.get(AUTH_TOKEN_KEY)
        return str(value or "").strip()

    async def set_token(self, token: str) -> None:
        clean = str(token or "").strip()
        if not clean:
            await self.clear_token()
            return
        await self._storage.set(AUTH_TOKEN_KEY, clean)

    async def clear_token(self) -> None:
        await self._storage.remove(AUTH_TOKEN_KEY)


__all__ = ["AUTH_TOKEN_KEY", "AuthTokenStorage"]
