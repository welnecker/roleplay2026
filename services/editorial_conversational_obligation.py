from __future__ import annotations

import re

_PENDING_KEY = "_pending_conversational_obligation"
_INVITATION = re.compile(
    r"\b(?:que tal|topa|aceita|vamos|podemos|quer(?:ia)?|bora|café|encontro)\b",
    re.IGNORECASE,
)


def detect_conversational_obligation(user_text: str) -> str:
    """Retém somente perguntas e convites que não podem desaparecer entre ponte e beat."""

    value = " ".join(str(user_text or "").split()).strip()
    if not value:
        return ""
    if "?" in value or _INVITATION.search(value):
        return value[:320]
    return ""


def pending_obligation(facts: dict[str, str]) -> str:
    return str(facts.get(_PENDING_KEY, "") or "").strip()


def store_pending_obligation(facts: dict[str, str], user_text: str) -> str:
    obligation = detect_conversational_obligation(user_text)
    if obligation:
        facts[_PENDING_KEY] = obligation
    return obligation


def consume_pending_obligation(facts: dict[str, str]) -> str:
    return str(facts.pop(_PENDING_KEY, "") or "").strip()


__all__ = [
    "consume_pending_obligation",
    "detect_conversational_obligation",
    "pending_obligation",
    "store_pending_obligation",
]
