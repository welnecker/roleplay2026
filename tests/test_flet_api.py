from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fastapi.testclient import TestClient

from flet_api.app import ApiServices, create_api_app
from flet_api.payments import PaymentState
from flet_api.runs import RunFrame
from flet_api.sessions import SessionStore
from persistence.accounts import AccountUser
from platform_core.models import AccessStatus, ProgressStatus, StoryCard


@dataclass
class FakeAccounts:
    user: AccountUser
    password: str = "senha-segura"
    entitled_packages: set[str] | None = None

    def register(self, *, email: str, password: str, display_name: str) -> AccountUser:
        if email.casefold() == self.user.email.casefold():
            raise ValueError("Já existe uma conta com este e-mail.")
        if len(password) < 8:
            raise ValueError("A senha deve ter ao menos 8 caracteres.")
        self.user = AccountUser("user-new", email.casefold(), display_name, "active")
        self.password = password
        return self.user

    def authenticate(self, *, email: str, password: str) -> AccountUser | None:
        if email.casefold() == self.user.email.casefold() and password == self.password:
            return self.user
        return None

    def get_user(self, *, user_id: str) -> AccountUser | None:
        return self.user if user_id == self.user.user_id else None

    def has_entitlement(self, *, user_id: str, package_id: str, access: str) -> bool:
        return user_id == self.user.user_id and package_id in (self.entitled_packages or set())


@dataclass
class FakePayments:
    master_user_id: str = "user-1"

    def master_test_available(self, *, user_id: str) -> bool:
        return user_id == self.master_user_id

    def approve_master_test(self, *, user: AccountUser, package_id: str) -> PaymentState:
        if not self.master_test_available(user_id=user.user_id):
            raise PermissionError("Não autorizado.")
        return PaymentState(package_id, "test-pay-1", "approved", True)

    def create_pix(self, *, user: AccountUser, package_id: str) -> PaymentState:
        return PaymentState(
            package_id,
            "pay-1",
            "pending",
            False,
            qr_code="pix-copia-cola",
            qr_code_base64="cXI=",
        )

    def refresh(self, *, user: AccountUser, payment_order_id: str) -> PaymentState:
        if payment_order_id != "pay-1":
            raise KeyError("Cobrança não encontrada.")
        return PaymentState("story.locked", payment_order_id, "approved", True)


class FakeRuns:
    def open(self, *, account: AccountUser, package_id: str) -> RunFrame:
        return RunFrame(
            "run-1",
            package_id,
            "quadro-1",
            "[QUADRO quadro-1]\n[DESCRIÇÃO]\nCena real.\n[FALA mary|Mary]\nOlá.\n[/QUADRO]",
            "",
            1,
            1,
            ("/api/v1/runs/image?package_id=story.free&image_id=mary1.webp",),
        )

    def advance(self, **kwargs) -> RunFrame:
        if kwargs["revealed_entries"] < 1:
            raise PermissionError("Revele todas as falas.")
        return RunFrame("run-1", kwargs["package_id"], "quadro-2", "[QUADRO quadro-2]\n[DESCRIÇÃO]\nContinuação.\n[/QUADRO]", "", 0, 0)

    def image(self, *, package_id: str, node_id: str = "", image_id: str = ""):
        return None


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
    primed: list[tuple[str, str]] = []
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
            payment_gateway=FakePayments(),
            paid_access_primer=lambda user_id, package_id: primed.append(
                (user_id, package_id)
            ),
            run_service=FakeRuns(),  # type: ignore[arg-type]
        )
    )
    app.state.primed_access = primed
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


def test_cadastro_cria_sessao_e_rejeita_email_duplicado() -> None:
    test_client, _accounts = client()

    created = test_client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Pessoa Nova",
            "email": "nova@example.com",
            "password": "senha-segura",
        },
    )
    duplicated = test_client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Outra Pessoa",
            "email": "nova@example.com",
            "password": "outra-senha",
        },
    )

    assert created.status_code == 201
    assert created.json()["access_token"]
    assert created.json()["user"] == {
        "user_id": "user-new",
        "email": "nova@example.com",
        "display_name": "Pessoa Nova",
    }
    assert duplicated.status_code == 400
    assert duplicated.json()["detail"] == "Já existe uma conta com este e-mail."


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


def test_pagamento_pix_e_teste_master_exigem_sessao() -> None:
    test_client, _accounts = client()
    token = login(test_client)
    headers = {"Authorization": f"Bearer {token}"}

    options = test_client.get("/api/v1/payments/story.locked/options", headers=headers)
    created = test_client.post(
        "/api/v1/payments/pix",
        headers=headers,
        json={"package_id": "story.locked"},
    )
    approved = test_client.post(
        "/api/v1/payments/master-test",
        headers=headers,
        json={"package_id": "story.locked"},
    )

    assert options.json()["master_test_available"] is True
    assert created.json()["qr_code"] == "pix-copia-cola"
    assert approved.json()["approved"] is True
    assert test_client.app.state.primed_access == [("user-1", "story.locked")]
    assert test_client.post(
        "/api/v1/payments/pix", json={"package_id": "story.locked"}
    ).status_code == 401


def test_inactive_user_invalidates_existing_session() -> None:
    test_client, accounts = client()
    token = login(test_client)
    accounts.user = AccountUser("user-1", "pessoa@example.com", "Pessoa", "disabled")

    response = test_client.get(
        "/api/v1/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


def test_run_abre_quadro_persistido_e_bloqueia_avanco_antecipado() -> None:
    test_client, _accounts = client()
    token = login(test_client)
    headers = {"Authorization": f"Bearer {token}"}

    opened = test_client.post(
        "/api/v1/runs/open",
        headers=headers,
        json={"package_id": "story.free"},
    )
    blocked = test_client.post(
        "/api/v1/runs/advance",
        headers=headers,
        json={"package_id": "story.free", "frame_id": "quadro-1", "revealed_entries": 0},
    )
    advanced = test_client.post(
        "/api/v1/runs/advance",
        headers=headers,
        json={"package_id": "story.free", "frame_id": "quadro-1", "revealed_entries": 1},
    )

    assert opened.status_code == 200
    assert opened.json()["frame_id"] == "quadro-1"
    assert opened.json()["entry_image_urls"][0].endswith(
        "/api/v1/runs/image?package_id=story.free&image_id=mary1.webp"
    )
    assert blocked.status_code == 403
    assert advanced.json()["frame_id"] == "quadro-2"
