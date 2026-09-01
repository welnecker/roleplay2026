import asyncio

from flet_client.auth_storage import AUTH_TOKEN_KEY, AuthTokenStorage


class FakeSecureStorage:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str) -> None:
        self.values[key] = value

    async def remove(self, key: str) -> None:
        self.values.pop(key, None)


def test_token_is_saved_restored_and_removed() -> None:
    backend = FakeSecureStorage()
    storage = AuthTokenStorage(backend)

    async def scenario() -> None:
        assert await storage.get_token() == ""
        await storage.set_token(" bearer-1 ")
        assert backend.values[AUTH_TOKEN_KEY] == "bearer-1"
        assert await storage.get_token() == "bearer-1"
        await storage.clear_token()
        assert await storage.get_token() == ""

    asyncio.run(scenario())
