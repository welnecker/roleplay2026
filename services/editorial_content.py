from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.editorial_publisher import publish_editorial_document
from persistence.spreadsheet_config import read_spreadsheet_ids
from services.pilot_supermarket import PilotScript


PACKAGE_ID = "roleplay2026.casada_frustrada"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"
EDITORIAL_PATH = PACKAGE_ROOT / "editorial_story.yaml"
_EDITORIAL_REPOSITORY: GoogleSheetsEditorialRepository | None = None
_EDITORIAL_READY = False


def build_editorial_repository(secrets: Any) -> GoogleSheetsEditorialRepository:
    global _EDITORIAL_REPOSITORY
    if _EDITORIAL_REPOSITORY is not None:
        return _EDITORIAL_REPOSITORY

    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("[gcp_service_account] não está configurado.")
    ids = read_spreadsheet_ids(secrets)
    _EDITORIAL_REPOSITORY = GoogleSheetsEditorialRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=ids.editorial,
    )
    return _EDITORIAL_REPOSITORY


def ensure_editorial_pilot(secrets: Any) -> GoogleSheetsEditorialRepository:
    """Garante o schema e publica a versão editorial somente quando necessário."""

    global _EDITORIAL_READY
    repository = build_editorial_repository(secrets)
    if _EDITORIAL_READY:
        return repository

    repository.ensure_schema()
    raw = yaml.safe_load(EDITORIAL_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("editorial_story.yaml inválido.")
    publish_editorial_document(repository, raw)
    _EDITORIAL_READY = True
    return repository


def load_editorial_pilot(secrets: Any) -> PilotScript:
    repository = ensure_editorial_pilot(secrets)
    return PilotScript(repository.load_pilot_raw(PACKAGE_ID))


def load_editorial_story_start(secrets: Any, package_id: str) -> tuple[str, str, str] | None:
    repository = ensure_editorial_pilot(secrets)
    story = repository.get_story(package_id)
    if story is None:
        return None
    return (
        str(story.get("script_version", "")),
        str(story.get("first_block_id", "")),
        str(story.get("first_beat_id", "")),
    )
