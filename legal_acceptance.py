from __future__ import annotations

from dataclasses import dataclass


TERMS_VERSION = "2026-09-15"
PRIVACY_VERSION = "2026-09-15"


@dataclass(frozen=True, slots=True)
class LegalAcceptance:
    terms_version: str
    privacy_version: str
    accepted_at: str

    @property
    def is_current(self) -> bool:
        return (
            self.terms_version == TERMS_VERSION
            and self.privacy_version == PRIVACY_VERSION
        )


__all__ = [
    "LegalAcceptance",
    "PRIVACY_VERSION",
    "TERMS_VERSION",
]
