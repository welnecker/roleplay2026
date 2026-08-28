from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock


@dataclass(frozen=True, slots=True)
class ApiSession:
    user_id: str
    expires_at: datetime


class SessionStore:
    """Sessões opacas e revogáveis; tokens brutos nunca ficam armazenados."""

    def __init__(self, *, ttl: timedelta = timedelta(hours=12)) -> None:
        if ttl.total_seconds() <= 0:
            raise ValueError("A duração da sessão deve ser positiva.")
        self.ttl = ttl
        self._sessions: dict[str, ApiSession] = {}
        self._lock = RLock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, *, user_id: str) -> tuple[str, ApiSession]:
        token = secrets.token_urlsafe(32)
        session = ApiSession(
            user_id=user_id,
            expires_at=datetime.now(UTC) + self.ttl,
        )
        with self._lock:
            self._sessions[self._digest(token)] = session
        return token, session

    def resolve(self, token: str) -> ApiSession | None:
        digest = self._digest(token)
        with self._lock:
            session = self._sessions.get(digest)
            if session is None:
                return None
            if session.expires_at <= datetime.now(UTC):
                self._sessions.pop(digest, None)
                return None
            return session

    def revoke(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(self._digest(token), None)

