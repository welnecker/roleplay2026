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

    def logout(self) -> None:
        if not self.access_token:
            return
        try:
            self._request("POST", "/api/v1/auth/logout")
        finally:
            self.access_token = ""


__all__ = ["ApiUser", "FletApiClient", "FletApiError"]
