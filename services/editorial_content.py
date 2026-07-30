from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.spreadsheet_config import read_spreadsheet_ids
from services.pilot_supermarket import PilotScript


PACKAGE_ID = "roleplay2026.casada_frustrada"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"
PILOT_PATH = PACKAGE_ROOT / "dialogue_pilot.yaml"


def build_editorial_repository(secrets: Any) -> GoogleSheetsEditorialRepository:
    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("[gcp_service_account] não está configurado.")
    ids = read_spreadsheet_ids(secrets)
    return GoogleSheetsEditorialRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=ids.editorial,
    )


def ensure_editorial_pilot(secrets: Any) -> GoogleSheetsEditorialRepository:
    """Cria o schema e publica o roteiro local somente na primeira inicialização."""

    repository = build_editorial_repository(secrets)
    repository.ensure_schema()
    if repository.get_story(PACKAGE_ID) is None:
        raw = yaml.safe_load(PILOT_PATH.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("dialogue_pilot.yaml inválido.")
        repository.seed_pilot(
            package_id=PACKAGE_ID,
            title="Casada frustrada",
            raw=raw,
        )
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
