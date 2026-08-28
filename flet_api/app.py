from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from flet_api.sessions import SessionStore
from persistence.accounts import AccountUser, build_account_repository
from platform_core.catalog import load_demo_catalog
from platform_core.models import AccessStatus, StoryCard
from services.secret_loader import load_application_secrets


class AccountRepository(Protocol):
    def authenticate(self, *, email: str, password: str) -> AccountUser | None: ...

    def get_user(self, *, user_id: str) -> AccountUser | None: ...

    def has_entitlement(self, *, user_id: str, package_id: str, access: str) -> bool: ...


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str
    password: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    display_name: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: UserResponse


class StoryCardResponse(BaseModel):
    package_id: str
    title: str
    subtitle: str
    description: str
    genres: list[str]
    access_status: str
    price_label: str
    chapter_label: str
    cover_url: str
    is_tasting: bool
    profile_name: str
    profile_identity: str
    profile_personality: str
    profile_intention: str
    replay_requires_purchase: bool


class CatalogResponse(BaseModel):
    items: list[StoryCardResponse]


@dataclass(slots=True)
class ApiServices:
    accounts: AccountRepository
    sessions: SessionStore
    catalog_loader: Callable[[], list[StoryCard]]


def _user_response(user: AccountUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
    )


def _card_response(card: StoryCard, *, access_status: AccessStatus) -> StoryCardResponse:
    return StoryCardResponse(
        package_id=card.package_id,
        title=card.title,
        subtitle=card.subtitle,
        description=card.description,
        genres=list(card.genres),
        access_status=access_status.value,
        price_label=card.price_label,
        chapter_label=card.chapter_label,
        cover_url=card.cover_url,
        is_tasting=card.is_tasting,
        profile_name=card.profile_name,
        profile_identity=card.profile_identity,
        profile_personality=card.profile_personality,
        profile_intention=card.profile_intention,
        replay_requires_purchase=card.replay_requires_purchase,
    )


def create_api_app(services: ApiServices) -> FastAPI:
    app = FastAPI(title="Roleplay 2026 Flet API", version="0.1.0")
    bearer = HTTPBearer(auto_error=False)

    def authenticated(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> tuple[AccountUser, str]:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado.")
        token = credentials.credentials.strip()
        session = services.sessions.resolve(token)
        if session is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessão inválida ou expirada.")
        user = services.accounts.get_user(user_id=session.user_id)
        if user is None or user.status != "active":
            services.sessions.revoke(token)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo ou inexistente.")
        return user, token

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/auth/login", response_model=LoginResponse)
    def login(payload: LoginRequest) -> LoginResponse:
        user = services.accounts.authenticate(email=payload.email, password=payload.password)
        if user is None or user.status != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")
        token, session = services.sessions.create(user_id=user.user_id)
        return LoginResponse(
            access_token=token,
            expires_at=session.expires_at.isoformat(),
            user=_user_response(user),
        )

    @app.get("/api/v1/auth/me", response_model=UserResponse)
    def me(identity: tuple[AccountUser, str] = Depends(authenticated)) -> UserResponse:
        user, _token = identity
        return _user_response(user)

    @app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
    def logout(identity: tuple[AccountUser, str] = Depends(authenticated)) -> None:
        _user, token = identity
        services.sessions.revoke(token)

    @app.get("/api/v1/catalog", response_model=CatalogResponse)
    def catalog(identity: tuple[AccountUser, str] = Depends(authenticated)) -> CatalogResponse:
        user, _token = identity
        items: list[StoryCardResponse] = []
        for card in services.catalog_loader():
            is_free = card.access_status == AccessStatus.FREE
            entitled = is_free or services.accounts.has_entitlement(
                user_id=user.user_id,
                package_id=card.package_id,
                access="free" if is_free else "paid",
            )
            access_status = (
                AccessStatus.FREE
                if is_free
                else AccessStatus.OWNED
                if entitled
                else AccessStatus.LOCKED
            )
            items.append(_card_response(card, access_status=access_status))
        return CatalogResponse(items=items)

    return app


_production_lock = Lock()
_production_app: FastAPI | None = None


def production_app() -> FastAPI:
    """Inicializa dependências reais somente quando a API for executada."""

    global _production_app
    if _production_app is None:
        with _production_lock:
            if _production_app is None:
                accounts = build_account_repository(load_application_secrets())
                _production_app = create_api_app(
                    ApiServices(
                        accounts=accounts,
                        sessions=SessionStore(),
                        catalog_loader=load_demo_catalog,
                    )
                )
    return _production_app

