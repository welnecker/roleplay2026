from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Literal, Protocol

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse, JSONResponse
from gspread.exceptions import APIError
from pydantic import BaseModel, ConfigDict, Field

from flet_api.sessions import SessionStore
from flet_api.payments import PaymentGateway, PaymentState, build_payment_gateway
from flet_api.runs import FletRunService, RunFrame
from persistence.accounts import AccountUser, build_account_repository
from persistence.google_sheets_retry import (
    GoogleSheetsTemporarilyUnavailable,
    api_error_status,
    is_quota_error,
)
from platform_core.catalog import INSTALLED_STORIES_ROOT, cover_file_for_package, load_demo_catalog
from platform_core.models import AccessStatus, StoryCard
from services.secret_loader import load_application_secrets


class AccountRepository(Protocol):
    def register(self, *, email: str, password: str, display_name: str) -> AccountUser: ...

    def authenticate(self, *, email: str, password: str) -> AccountUser | None: ...

    def get_user(self, *, user_id: str) -> AccountUser | None: ...

    def has_entitlement(self, *, user_id: str, package_id: str, access: str) -> bool: ...


class LoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str
    password: str


class RegisterRequest(LoginRequest):
    display_name: str


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


class PaymentRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    package_id: str


class PaymentRefreshRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    payment_order_id: str


class PaymentResponse(BaseModel):
    package_id: str
    payment_order_id: str
    status: str
    approved: bool
    qr_code: str = ""
    qr_code_base64: str = ""
    ticket_url: str = ""
    master_test_available: bool = False


class RunIdentityRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    package_id: str
    preferred_name: str = Field(min_length=1)
    story_gender: Literal["Como homem", "Como mulher", "De forma neutra"]


class RunOpenRequest(RunIdentityRequest):
    pass


class RunAdvanceRequest(RunIdentityRequest):
    frame_id: str
    revealed_entries: int


class RunRevealRequest(RunIdentityRequest):
    frame_id: str


class RunFrameResponse(BaseModel):
    run_id: str
    package_id: str
    frame_id: str
    content: str
    image_url: str
    entry_image_urls: list[str]
    revealed_entries: int
    entry_count: int
    finished: bool


class RunProfileResponse(BaseModel):
    completed: bool
    preferred_name: str
    story_gender: str


@dataclass(slots=True)
class ApiServices:
    accounts: AccountRepository
    sessions: SessionStore
    catalog_loader: Callable[[], list[StoryCard]]
    cover_resolver: Callable[[str], Path | None] = cover_file_for_package
    payment_gateway: PaymentGateway | None = None
    paid_access_resolver: Callable[[str, str], bool] | None = None
    paid_access_primer: Callable[[str, str], None] | None = None
    run_service: FletRunService | None = None


def _user_response(user: AccountUser) -> UserResponse:
    return UserResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
    )


def _card_response(
    card: StoryCard,
    *,
    access_status: AccessStatus,
    cover_url: str,
) -> StoryCardResponse:
    return StoryCardResponse(
        package_id=card.package_id,
        title=card.title,
        subtitle=card.subtitle,
        description=card.description,
        genres=list(card.genres),
        access_status=access_status.value,
        price_label=card.price_label,
        chapter_label=card.chapter_label,
        cover_url=cover_url,
        is_tasting=card.is_tasting,
        profile_name=card.profile_name,
        profile_identity=card.profile_identity,
        profile_personality=card.profile_personality,
        profile_intention=card.profile_intention,
        replay_requires_purchase=card.replay_requires_purchase,
    )


def _payment_response(
    state: PaymentState,
    *,
    master_test_available: bool,
) -> PaymentResponse:
    return PaymentResponse(
        package_id=state.package_id,
        payment_order_id=state.payment_order_id,
        status=state.status,
        approved=state.approved,
        qr_code=state.qr_code,
        qr_code_base64=state.qr_code_base64,
        ticket_url=state.ticket_url,
        master_test_available=master_test_available,
    )


def _run_response(frame: RunFrame, request: Request) -> RunFrameResponse:
    base_url = str(request.base_url).rstrip("/")

    def absolute(url: str) -> str:
        return base_url + url if url.startswith("/") else url

    image_url = absolute(frame.image_url)
    return RunFrameResponse(
        run_id=frame.run_id,
        package_id=frame.package_id,
        frame_id=frame.frame_id,
        content=frame.content,
        image_url=image_url,
        entry_image_urls=[absolute(url) for url in frame.entry_image_urls],
        revealed_entries=frame.revealed_entries,
        entry_count=frame.entry_count,
        finished=frame.finished,
    )


def create_api_app(services: ApiServices) -> FastAPI:
    app = FastAPI(title="Roleplay 2026 Flet API", version="0.1.0")
    bearer = HTTPBearer(auto_error=False)

    def sheets_unavailable_response(message: str) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": message},
            headers={"Retry-After": "15"},
        )

    @app.exception_handler(GoogleSheetsTemporarilyUnavailable)
    async def handle_sheets_unavailable(
        _request: Request,
        exc: GoogleSheetsTemporarilyUnavailable,
    ) -> JSONResponse:
        return sheets_unavailable_response(str(exc))

    @app.exception_handler(APIError)
    async def handle_raw_sheets_error(
        _request: Request,
        exc: APIError,
    ) -> JSONResponse:
        if is_quota_error(exc) or api_error_status(exc) in {500, 502, 503, 504}:
            return sheets_unavailable_response(
                "O armazenamento está temporariamente ocupado. "
                "Seu progresso foi preservado; tente novamente em alguns segundos."
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Falha de configuração do armazenamento."},
        )

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

    @app.post(
        "/api/v1/auth/register",
        response_model=LoginResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def register(payload: RegisterRequest) -> LoginResponse:
        try:
            user = services.accounts.register(
                email=payload.email,
                password=payload.password,
                display_name=payload.display_name,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
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
    def catalog(
        request: Request,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> CatalogResponse:
        user, _token = identity
        items: list[StoryCardResponse] = []
        for card in services.catalog_loader():
            is_free = card.access_status == AccessStatus.FREE
            if services.paid_access_resolver is not None and not is_free:
                entitled = services.paid_access_resolver(user.user_id, card.package_id)
            else:
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
            cover_url = ""
            if services.cover_resolver(card.package_id) is not None:
                cover_url = str(
                    request.url_for("catalog_cover", package_id=card.package_id)
                )
            items.append(
                _card_response(
                    card,
                    access_status=access_status,
                    cover_url=cover_url,
                )
            )
        return CatalogResponse(items=items)

    @app.get("/api/v1/catalog/{package_id}/cover", name="catalog_cover")
    def catalog_cover(package_id: str) -> FileResponse:
        cover = services.cover_resolver(package_id)
        if cover is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capa não encontrada.")
        return FileResponse(cover)

    def payment_gateway() -> PaymentGateway:
        if services.payment_gateway is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Pagamento ainda não está configurado neste servidor.",
            )
        return services.payment_gateway

    @app.get("/api/v1/payments/{package_id}/options", response_model=PaymentResponse)
    def payment_options(
        package_id: str,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> PaymentResponse:
        user, _token = identity
        gateway = payment_gateway()
        return PaymentResponse(
            package_id=package_id,
            payment_order_id="",
            status="not_started",
            approved=False,
            master_test_available=gateway.master_test_available(user_id=user.user_id),
        )

    @app.post("/api/v1/payments/master-test", response_model=PaymentResponse)
    def approve_master_test(
        payload: PaymentRequest,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> PaymentResponse:
        user, _token = identity
        gateway = payment_gateway()
        try:
            state = gateway.approve_master_test(user=user, package_id=payload.package_id)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc).strip("'")) from exc
        if state.approved and services.paid_access_primer is not None:
            services.paid_access_primer(user.user_id, state.package_id)
        return _payment_response(state, master_test_available=True)

    @app.post("/api/v1/payments/pix", response_model=PaymentResponse)
    def create_pix(
        payload: PaymentRequest,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> PaymentResponse:
        user, _token = identity
        gateway = payment_gateway()
        try:
            state = gateway.create_pix(user=user, package_id=payload.package_id)
        except (KeyError, ValueError, PermissionError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc).strip("'")) from exc
        if state.approved and services.paid_access_primer is not None:
            services.paid_access_primer(user.user_id, state.package_id)
        return _payment_response(
            state,
            master_test_available=gateway.master_test_available(user_id=user.user_id),
        )

    @app.post("/api/v1/payments/refresh", response_model=PaymentResponse)
    def refresh_payment(
        payload: PaymentRefreshRequest,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> PaymentResponse:
        user, _token = identity
        gateway = payment_gateway()
        try:
            state = gateway.refresh(user=user, payment_order_id=payload.payment_order_id)
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc).strip("'")) from exc
        if state.approved and services.paid_access_primer is not None:
            services.paid_access_primer(user.user_id, state.package_id)
        return _payment_response(
            state,
            master_test_available=gateway.master_test_available(user_id=user.user_id),
        )

    def run_service() -> FletRunService:
        if services.run_service is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Runtime ainda não está configurado neste servidor.",
            )
        return services.run_service

    @app.get(
        "/api/v1/runs/{package_id}/profile",
        response_model=RunProfileResponse,
    )
    def run_profile(
        package_id: str,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> RunProfileResponse:
        user, _token = identity
        if not any(card.package_id == package_id for card in services.catalog_loader()):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="História não encontrada.",
            )
        try:
            profile = run_service().profile(account=user, package_id=package_id)
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc).strip("'"),
            ) from exc
        return RunProfileResponse(
            completed=profile.completed,
            preferred_name=profile.preferred_name,
            story_gender=profile.story_gender,
        )

    @app.post("/api/v1/runs/open", response_model=RunFrameResponse)
    def open_run(
        payload: RunOpenRequest,
        request: Request,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> RunFrameResponse:
        user, _token = identity
        selected_card = next(
            (card for card in services.catalog_loader() if card.package_id == payload.package_id),
            None,
        )
        if selected_card is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="História não encontrada.")
        is_free = selected_card.access_status == AccessStatus.FREE
        if (
            not is_free
            and services.paid_access_resolver is not None
            and not services.paid_access_resolver(user.user_id, payload.package_id)
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="História sem acesso liberado.")
        try:
            frame = run_service().open(
                account=user,
                package_id=payload.package_id,
                preferred_name=payload.preferred_name,
                story_gender=payload.story_gender,
            )
        except (KeyError, ValueError, PermissionError, RuntimeError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc).strip("'")) from exc
        return _run_response(frame, request)

    @app.post("/api/v1/runs/advance", response_model=RunFrameResponse)
    def advance_run(
        payload: RunAdvanceRequest,
        request: Request,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> RunFrameResponse:
        user, _token = identity
        try:
            frame = run_service().advance(
                account=user,
                package_id=payload.package_id,
                expected_frame_id=payload.frame_id,
                revealed_entries=payload.revealed_entries,
                preferred_name=payload.preferred_name,
                story_gender=payload.story_gender,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc).strip("'")) from exc
        return _run_response(frame, request)

    @app.post("/api/v1/runs/reveal", response_model=RunFrameResponse)
    def reveal_run_entry(
        payload: RunRevealRequest,
        request: Request,
        identity: tuple[AccountUser, str] = Depends(authenticated),
    ) -> RunFrameResponse:
        user, _token = identity
        try:
            frame = run_service().reveal(
                account=user,
                package_id=payload.package_id,
                expected_frame_id=payload.frame_id,
                preferred_name=payload.preferred_name,
                story_gender=payload.story_gender,
            )
        except (KeyError, ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc).strip("'")) from exc
        return _run_response(frame, request)

    @app.get("/api/v1/runs/image")
    def run_image(
        package_id: str,
        node_id: str = "",
        image_id: str = "",
    ) -> FileResponse:
        image = run_service().image(
            package_id=package_id,
            node_id=node_id,
            image_id=image_id,
        )
        if image is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Imagem não encontrada.")
        return FileResponse(image)

    return app


_production_lock = Lock()
_production_app: FastAPI | None = None


def production_app() -> FastAPI:
    """Inicializa dependências reais somente quando a API for executada."""

    global _production_app
    if _production_app is None:
        with _production_lock:
            if _production_app is None:
                secrets = load_application_secrets()
                accounts = build_account_repository(secrets)
                payment_gateway = build_payment_gateway(
                    secrets,
                    accounts=accounts,
                    stories_root=INSTALLED_STORIES_ROOT,
                )
                run_gateway = FletRunService(secrets)

                def has_paid_access(user_id: str, package_id: str) -> bool:
                    from services.paid_run_access import get_paid_run_access

                    return get_paid_run_access(
                        secrets=secrets,
                        user_id=user_id,
                        package_id=package_id,
                    ).allowed

                def prime_paid_access(user_id: str, package_id: str) -> None:
                    from services.paid_run_access import prime_paid_access_available

                    prime_paid_access_available(
                        secrets=secrets,
                        user_id=user_id,
                        package_id=package_id,
                        ttl_seconds=90.0,
                    )

                _production_app = create_api_app(
                    ApiServices(
                        accounts=accounts,
                        sessions=SessionStore(),
                        catalog_loader=load_demo_catalog,
                        payment_gateway=payment_gateway,
                        paid_access_resolver=has_paid_access,
                        paid_access_primer=prime_paid_access,
                        run_service=run_gateway,
                    )
                )
    return _production_app
