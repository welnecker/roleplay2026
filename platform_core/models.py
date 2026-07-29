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
