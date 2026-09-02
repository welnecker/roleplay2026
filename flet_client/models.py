from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccessStatus(StrEnum):
    FREE = "free"
    OWNED = "owned"
    LOCKED = "locked"


class ProgressStatus(StrEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class StoryCard:
    """Contrato público do card recebido pelo cliente instalável.

    O cliente mantém uma cópia pequena desse contrato para que o pacote Android
    e Windows não precise levar os módulos e dependências privadas do backend.
    """

    package_id: str
    title: str
    subtitle: str
    description: str
    genres: tuple[str, ...]
    access_status: AccessStatus
    progress_status: ProgressStatus
    price_label: str = ""
    chapter_label: str = ""
    cover_url: str = ""
    is_tasting: bool = False
    profile_name: str = ""
    profile_identity: str = ""
    profile_personality: str = ""
    profile_intention: str = ""
    replay_requires_purchase: bool = False


__all__ = ["AccessStatus", "ProgressStatus", "StoryCard"]
