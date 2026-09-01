from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets as pysecrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Any


@dataclass(frozen=True, slots=True)
class ApiSession:
    user_id: str
    expires_at: datetime


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padded = value + ("=" * (-len(value) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _derive_key(value: str) -> bytes:
    return hashlib.sha256(
        b"roleplay2026-flet-session-v1\0" + value.encode("utf-8")
    ).digest()


def _configured_signing_key() -> bytes:
    """Resolve uma chave estável sem introduzir um novo segredo obrigatório.

    Produção pode definir ``FLET_SESSION_SIGNING_KEY`` explicitamente. Quando não
    define, derivamos uma subchave do private_key da service account já existente;
    ela nunca é enviada ao cliente e a derivação é separada por domínio. Em
    ambientes de teste sem secrets usamos uma chave aleatória de processo.
    """

    explicit = str(os.getenv("FLET_SESSION_SIGNING_KEY", "") or "").strip()
    if explicit:
        return _derive_key(explicit)

    try:
        from services.secret_loader import load_application_secrets

        values: dict[str, Any] = load_application_secrets()
    except Exception:
        values = {}

    configured = str(values.get("FLET_SESSION_SIGNING_KEY", "") or "").strip()
    if configured:
        return _derive_key(configured)

    service_account = values.get("gcp_service_account")
    if isinstance(service_account, dict):
        private_key = str(service_account.get("private_key", "") or "").strip()
        if private_key:
            return _derive_key(private_key)

    return pysecrets.token_bytes(32)


class SessionStore:
    """Sessões assinadas, expiradas e revogáveis que sobrevivem a redeploys.

    O servidor não precisa guardar cada token em RAM para validá-lo. Isso evita que
    um restart/redeploy do Render derrube usuários autenticados. Logout continua
    revogando imediatamente o token no processo atual; o cliente também remove a
    credencial persistida, e toda sessão expira pelo TTL embutido no token.
    """

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(hours=12),
        signing_key: bytes | str | None = None,
    ) -> None:
        if ttl.total_seconds() <= 0:
            raise ValueError("A duração da sessão deve ser positiva.")
        self.ttl = ttl
        if isinstance(signing_key, str):
            resolved = _derive_key(signing_key)
        elif isinstance(signing_key, bytes):
            resolved = signing_key
        else:
            resolved = _configured_signing_key()
        if len(resolved) < 32:
            resolved = hashlib.sha256(resolved).digest()
        self._signing_key = resolved
        self._revoked: dict[str, datetime] = {}
        self._lock = RLock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _signature(self, encoded_payload: str) -> str:
        signature = hmac.new(
            self._signing_key,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return _b64encode(signature)

    def _prune_revoked(self, now: datetime) -> None:
        expired = [digest for digest, expires_at in self._revoked.items() if expires_at <= now]
        for digest in expired:
            self._revoked.pop(digest, None)

    def create(self, *, user_id: str) -> tuple[str, ApiSession]:
        now = datetime.now(UTC)
        session = ApiSession(
            user_id=str(user_id or "").strip(),
            expires_at=now + self.ttl,
        )
        payload = {
            "v": 1,
            "uid": session.user_id,
            "exp": int(session.expires_at.timestamp()),
            "n": pysecrets.token_urlsafe(16),
        }
        encoded_payload = _b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        token = f"v1.{encoded_payload}.{self._signature(encoded_payload)}"
        return token, session

    def resolve(self, token: str) -> ApiSession | None:
        clean = str(token or "").strip()
        try:
            version, encoded_payload, supplied_signature = clean.split(".", 2)
        except ValueError:
            return None
        if version != "v1":
            return None
        expected_signature = self._signature(encoded_payload)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None

        try:
            payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
            user_id = str(payload.get("uid", "") or "").strip()
            expires_at = datetime.fromtimestamp(int(payload.get("exp", 0) or 0), tz=UTC)
        except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if payload.get("v") != 1 or not user_id:
            return None

        now = datetime.now(UTC)
        if expires_at <= now:
            return None
        digest = self._digest(clean)
        with self._lock:
            self._prune_revoked(now)
            if digest in self._revoked:
                return None
        return ApiSession(user_id=user_id, expires_at=expires_at)

    def revoke(self, token: str) -> None:
        clean = str(token or "").strip()
        if not clean:
            return
        session = self.resolve(clean)
        if session is None:
            return
        with self._lock:
            self._revoked[self._digest(clean)] = session.expires_at

