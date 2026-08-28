from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from flet_api.app import ApiServices, create_api_app
from flet_api.sessions import SessionStore
from persistence.accounts import AccountUser
from platform_core.models import AccessStatus, ProgressStatus, StoryCard


@dataclass
class FakeAccounts:
    user: AccountUser
    password: str = "senha-segura"
    entitled_packages: set[str] | None = None

    def authenticate(self, *, email: str, password: str) -> AccountUser | None:
        if email.casefold() == self.user.email.casefold() and password == self.password:
            return self.user
        return None

    def get_user(self, *, user_id: str) -> AccountUser | None:
        return self.user if user_id == self.user.user_id else None

    def has_entitlement(self, *, user_id: str, package_id: str, access: str) -> bool:
        return user_id == self.user.user_id and package_id in (self.entitled_packages or set())


def card(package_id: str, access: AccessStatus) -> StoryCard:
    return StoryCard(
        package_id=package_id,
        title=package_id,
        subtitle="Subtítulo",
        description="Descrição pública",
        genres=("Romance",),
        access_status=access,
        progress_status=ProgressStatus.NOT_STARTED,
        price_label="" if access == AccessStatus.FREE else "R$ 9,90",
        cover_url="data:image/webp;base64,Y2FwYQ==",
    )


def client(*, entitled_packages: set[str] | None = None) -> tuple[TestClient, FakeAccounts]:
    accounts = FakeAccounts(
        user=AccountUser("user-1", "pessoa@example.com", "Pessoa", "active"),
        entitled_packages=entitled_packages,
    )
    app = create_api_app(
        ApiServices(
            accounts=accounts,
            sessions=SessionStore(),
            catalog_loader=lambda: [
                card("story.free", AccessStatus.FREE),
                card("story.owned", AccessStatus.LOCKED),
                card("story.locked", AccessStatus.LOCKED),
            ],
            cover_resolver=lambda _package_id: Path(__file__),
        )
    )
    return TestClient(app), accounts


def login(test_client: TestClient) -> str:
    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "pessoa@example.com", "password": "senha-segura"},
    )
    assert response.status_code == 200
    return str(response.json()["access_token"])


def test_login_returns_opaque_bearer_and_current_user() -> None:
    test_client, _accounts = client()

    response = test_client.post(
        "/api/v1/auth/login",
        json={"email": "pessoa@example.com", "password": "senha-segura"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert "senha-segura" not in response.text
    me = test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert me.json() == {
        "user_id": "user-1",
        "email": "pessoa@example.com",
        "display_name": "Pessoa",
    }


def test_invalid_credentials_and_missing_token_are_rejected() -> None:
    test_client, _accounts = client()

    invalid = test_client.post(
        "/api/v1/auth/login",
        json={"email": "pessoa@example.com", "password": "errada"},
    )
    catalog = test_client.get("/api/v1/catalog")

    assert invalid.status_code == 401
    assert catalog.status_code == 401


def test_catalog_marks_free_owned_and_locked_server_side() -> None:
    test_client, _accounts = client(entitled_packages={"story.owned"})
    token = login(test_client)

    response = test_client.get(
        "/api/v1/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    items = {item["package_id"]: item for item in response.json()["items"]}
    assert items["story.free"]["access_status"] == "free"
    assert items["story.owned"]["access_status"] == "owned"
    assert items["story.locked"]["access_status"] == "locked"
    assert items["story.owned"]["cover_url"].endswith(
        "/api/v1/catalog/story.owned/cover"
    )
    assert set(items["story.owned"]) == {
        "package_id", "title", "subtitle", "description", "genres",
        "access_status", "price_label", "chapter_label", "cover_url",
        "is_tasting", "profile_name", "profile_identity",
        "profile_personality", "profile_intention", "replay_requires_purchase",
    }

    cover = test_client.get("/api/v1/catalog/story.owned/cover")
    assert cover.status_code == 200
    assert cover.content == Path(__file__).read_bytes()


def test_logout_revokes_session() -> None:
    test_client, _accounts = client()
    token = login(test_client)
    headers = {"Authorization": f"Bearer {token}"}

    assert test_client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert test_client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_inactive_user_invalidates_existing_session() -> None:
    test_client, accounts = client()
    token = login(test_client)
    accounts.user = AccountUser("user-1", "pessoa@example.com", "Pessoa", "disabled")

    response = test_client.get(
        "/api/v1/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
