from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.editorial_publisher import publish_editorial_document
from persistence.spreadsheet_config import read_spreadsheet_ids
import services.pilot_supermarket as pilot_supermarket_module
from services.pilot_supermarket import PilotScript
from services.supermarket_script_v2 import (
    clean_supermarket_script_v2_response,
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


PACKAGE_ID = "roleplay2026.casada_frustrada"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"
EDITORIAL_PATH = PACKAGE_ROOT / "supermarket_pilot.yaml"
_EDITORIAL_REPOSITORY: GoogleSheetsEditorialRepository | None = None
_EDITORIAL_READY = False
_FREE_TEXT_KEYS = {
    "introduction",
    "title",
    "required_movement",
    "canonical_line",
    "dramatic_direction",
    "text",
}
_FREE_TEXT_PATTERN = re.compile(
    r"^(?P<indent>\s*)(?P<key>" + "|".join(sorted(_FREE_TEXT_KEYS)) + r"):\s*(?P<value>.*)$"
)

pilot_supermarket_module.decide_turn = decide_supermarket_script_v2_turn
pilot_supermarket_module.clean_model_response = clean_supermarket_script_v2_response


def _protect_editorial_plain_scalars(text: str) -> str:
    protected: list[str] = []
    for line in text.splitlines():
        match = _FREE_TEXT_PATTERN.match(line)
        if match is None:
            protected.append(line)
            continue
        value = match.group("value")
        stripped = value.lstrip()
        if not stripped or stripped.startswith(("'", '"', "|", ">", "[", "{")):
            protected.append(line)
            continue
        protected.append(
            f'{match.group("indent")}{match.group("key")}: '
            f'{json.dumps(value, ensure_ascii=False)}'
        )
    return "\n".join(protected) + ("\n" if text.endswith("\n") else "")


def load_editorial_yaml_text(text: str) -> dict[str, Any]:
    raw = yaml.safe_load(_protect_editorial_plain_scalars(text))
    if not isinstance(raw, dict):
        raise ValueError("supermarket_pilot.yaml inválido.")
    return raw


def load_source_document() -> dict[str, Any]:
    return load_editorial_yaml_text(EDITORIAL_PATH.read_text(encoding="utf-8"))


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
    """Espelha a mesma fonte executável em ROLEPLAY_EDITORIAL."""

    global _EDITORIAL_READY
    repository = build_editorial_repository(secrets)
    if _EDITORIAL_READY:
        return repository
    repository.ensure_schema()
    publish_editorial_document(repository, load_source_document())
    _EDITORIAL_READY = True
    return repository


def load_editorial_pilot(secrets: Any) -> PilotScript:
    """Carrega o piloto diretamente da fonte; a planilha não participa do turno."""

    ensure_editorial_pilot(secrets)
    return prepare_supermarket_script_v2(PilotScript(load_source_document()))


def load_editorial_story_start(secrets: Any, package_id: str) -> tuple[str, str, str] | None:
    if package_id != PACKAGE_ID:
        return None
    ensure_editorial_pilot(secrets)
    raw = load_source_document()
    blocks = [item for item in raw.get("blocks", []) if isinstance(item, dict)]
    if not blocks:
        return None
    first = min(blocks, key=lambda item: int(item.get("order", 0) or 0))
    return (
        str(raw.get("script_version", "")),
        str(first.get("block_id", "")),
        str(first.get("entry_beat_id", "")),
    )
