from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True, slots=True)
class SaveRecord:
    save_id: str
    user_id: str
    package_id: str
    package_version: str
    state_version: int
    state: dict[str, Any]
    status: str
    created_at: str
    updated_at: str


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    save_id: str
    user_id: str
    package_id: str
    instance_id: str
    status: str
    started_at: str
    last_seen_at: str
    ended_at: str = ""


@dataclass(frozen=True, slots=True)
class InteractionRecord:
    interaction_id: str
    session_id: str
    save_id: str
    user_id: str
    package_id: str
    role: str
    content: str
    sequence: int
    created_at: str
    metadata: dict[str, Any]


class ConcurrentSaveUpdateError(RuntimeError):
    """O save foi alterado por outra instância antes desta gravação."""
