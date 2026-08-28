from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from platform_core.models import AccessStatus, ProgressStatus, StoryCard


class FletApiError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ApiUser:
    user_id: str
    email: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ApiPayment:
    package_id: str
    payment_order_id: str
    status: str
    approved: bool
    qr_code: str
    qr_code_base64: str
    ticket_url: str
    master_test_available: bool


@dataclass(frozen=True, slots=True)
class ApiRunFrame:
    run_id: str
    package_id: str
    frame_id: str
    content: str
    image_url: str
    entry_image_urls: tuple[str, ...]
    revealed_entries: int
    entry_count: int
    finished: bool


class FletApiClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
        session: requests.Session | None = None,
    ) -> None:
        value = str(base_url or "").strip().rstrip("/")
        if not value:
            raise ValueError("URL da API Flet não configurada.")
        self.base_url = value
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.access_token = ""

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout_seconds,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise FletApiError("Não foi possível conectar à API do Entre Cenas.") from exc
        if response.status_code >= 400:
            try:
                detail = str(response.json().get("detail", "") or "").strip()
            except (ValueError, AttributeError):
                detail = ""
            raise FletApiError(detail or f"A API respondeu com erro {response.status_code}.")
        return response

    def login(self, *, email: str, password: str) -> ApiUser:
        response = self._request(
            "POST",
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        payload = response.json()
        token = str(payload.get("access_token", "") or "").strip()
        user = payload.get("user") or {}
        if not token or not isinstance(user, dict):
            raise FletApiError("Resposta de autenticação inválida.")
        self.access_token = token
        return ApiUser(
            user_id=str(user.get("user_id", "") or ""),
            email=str(user.get("email", "") or ""),
            display_name=str(user.get("display_name", "") or ""),
        )

    def register(self, *, display_name: str, email: str, password: str) -> ApiUser:
        response = self._request(
            "POST",
            "/api/v1/auth/register",
            json={
                "display_name": display_name,
                "email": email,
                "password": password,
            },
        )
        payload = response.json()
        token = str(payload.get("access_token", "") or "").strip()
        user = payload.get("user") or {}
        if not token or not isinstance(user, dict):
            raise FletApiError("Resposta de cadastro inválida.")
        self.access_token = token
        return ApiUser(
            user_id=str(user.get("user_id", "") or ""),
            email=str(user.get("email", "") or ""),
            display_name=str(user.get("display_name", "") or ""),
        )

    def catalog(self) -> list[StoryCard]:
        response = self._request("GET", "/api/v1/catalog")
        payload = response.json()
        rows = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise FletApiError("Resposta de catálogo inválida.")
        result: list[StoryCard] = []
        for row in rows:
            if not isinstance(row, dict):
                raise FletApiError("Card inválido recebido da API.")
            try:
                access_status = AccessStatus(str(row.get("access_status", "")))
            except ValueError as exc:
                raise FletApiError("Status de acesso inválido recebido da API.") from exc
            result.append(
                StoryCard(
                    package_id=str(row.get("package_id", "") or ""),
                    title=str(row.get("title", "") or ""),
                    subtitle=str(row.get("subtitle", "") or ""),
                    description=str(row.get("description", "") or ""),
                    genres=tuple(str(item) for item in row.get("genres", []) or []),
                    access_status=access_status,
                    progress_status=ProgressStatus.NOT_STARTED,
                    price_label=str(row.get("price_label", "") or ""),
                    chapter_label=str(row.get("chapter_label", "") or ""),
                    cover_url=str(row.get("cover_url", "") or ""),
                    is_tasting=bool(row.get("is_tasting", False)),
                    profile_name=str(row.get("profile_name", "") or ""),
                    profile_identity=str(row.get("profile_identity", "") or ""),
                    profile_personality=str(row.get("profile_personality", "") or ""),
                    profile_intention=str(row.get("profile_intention", "") or ""),
                    replay_requires_purchase=bool(row.get("replay_requires_purchase", False)),
                )
            )
        return result

    @staticmethod
    def _payment(response: requests.Response) -> ApiPayment:
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("package_id"):
            raise FletApiError("Resposta de pagamento inválida.")
        return ApiPayment(
            package_id=str(payload.get("package_id", "") or ""),
            payment_order_id=str(payload.get("payment_order_id", "") or ""),
            status=str(payload.get("status", "") or ""),
            approved=bool(payload.get("approved", False)),
            qr_code=str(payload.get("qr_code", "") or ""),
            qr_code_base64=str(payload.get("qr_code_base64", "") or ""),
            ticket_url=str(payload.get("ticket_url", "") or ""),
            master_test_available=bool(payload.get("master_test_available", False)),
        )

    def payment_options(self, package_id: str) -> ApiPayment:
        return self._payment(self._request("GET", f"/api/v1/payments/{package_id}/options"))

    def approve_master_test(self, package_id: str) -> ApiPayment:
        return self._payment(
            self._request("POST", "/api/v1/payments/master-test", json={"package_id": package_id})
        )

    def create_pix(self, package_id: str) -> ApiPayment:
        return self._payment(
            self._request("POST", "/api/v1/payments/pix", json={"package_id": package_id})
        )

    def refresh_payment(self, payment_order_id: str) -> ApiPayment:
        return self._payment(
            self._request(
                "POST",
                "/api/v1/payments/refresh",
                json={"payment_order_id": payment_order_id},
            )
        )

    @staticmethod
    def _run_frame(response: requests.Response) -> ApiRunFrame:
        payload = response.json()
        if not isinstance(payload, dict) or not payload.get("frame_id"):
            raise FletApiError("Resposta de run inválida.")
        return ApiRunFrame(
            run_id=str(payload.get("run_id", "") or ""),
            package_id=str(payload.get("package_id", "") or ""),
            frame_id=str(payload.get("frame_id", "") or ""),
            content=str(payload.get("content", "") or ""),
            image_url=str(payload.get("image_url", "") or ""),
            entry_image_urls=tuple(
                str(item or "")
                for item in payload.get("entry_image_urls", []) or []
            ),
            revealed_entries=int(payload.get("revealed_entries", 0) or 0),
            entry_count=int(payload.get("entry_count", 0) or 0),
            finished=bool(payload.get("finished", False)),
        )

    def open_run(self, package_id: str) -> ApiRunFrame:
        return self._run_frame(
            self._request("POST", "/api/v1/runs/open", json={"package_id": package_id})
        )

    def advance_run(
        self,
        *,
        package_id: str,
        frame_id: str,
        revealed_entries: int,
    ) -> ApiRunFrame:
        return self._run_frame(
            self._request(
                "POST",
                "/api/v1/runs/advance",
                json={
                    "package_id": package_id,
                    "frame_id": frame_id,
                    "revealed_entries": revealed_entries,
                },
            )
        )

    def reveal_run_entry(self, *, package_id: str, frame_id: str) -> ApiRunFrame:
        return self._run_frame(
            self._request(
                "POST",
                "/api/v1/runs/reveal",
                json={"package_id": package_id, "frame_id": frame_id},
            )
        )

    def logout(self) -> None:
        if not self.access_token:
            return
        try:
            self._request("POST", "/api/v1/auth/logout")
        finally:
            self.access_token = ""


__all__ = ["ApiPayment", "ApiRunFrame", "ApiUser", "FletApiClient", "FletApiError"]
