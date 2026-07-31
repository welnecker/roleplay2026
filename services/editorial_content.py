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
from services.private_thought_pilot import (
    apply_private_thought_overrides,
    decide_private_thought_turn,
    prepare_private_thought_script,
)
from services.pilot_supermarket import PilotScript


PACKAGE_ID = "roleplay2026.casada_frustrada"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"
EDITORIAL_PATH = PACKAGE_ROOT / "editorial_story.yaml"
_EDITORIAL_REPOSITORY: GoogleSheetsEditorialRepository | None = None
_EDITORIAL_READY = False
_FREE_TEXT_KEYS = {
    "introduction",
    "title",
    "required_movement",
    "canonical_line",
    "dramatic_direction",
}
_FREE_TEXT_PATTERN = re.compile(
    r"^(?P<indent>\s*)(?P<key>" + "|".join(sorted(_FREE_TEXT_KEYS)) + r"):\s*(?P<value>.*)$"
)

# A página importa ``decide_turn`` do módulo original depois de importar este módulo.
# A substituição mantém um único player e adiciona as correções incrementais do piloto.
pilot_supermarket_module.decide_turn = decide_private_thought_turn


def _protect_editorial_plain_scalars(text: str) -> str:
    """Protege textos livres que podem conter dois-pontos e aspas.

    O roteiro é produzido para leitura humana e usa escalares simples. Falas como
    ``Vou mandar mensagem: Oi`` são ambíguas para YAML. Antes do parse, esses
    campos são convertidos para strings JSON, que também são escalares YAML válidos.
    """

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
        raise ValueError("editorial_story.yaml inválido.")
    return raw


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
    raw = load_editorial_yaml_text(EDITORIAL_PATH.read_text(encoding="utf-8"))
    publish_editorial_document(repository, apply_private_thought_overrides(raw))
    _EDITORIAL_READY = True
    return repository


def load_editorial_pilot(secrets: Any) -> PilotScript:
    repository = ensure_editorial_pilot(secrets)
    script = PilotScript(repository.load_pilot_raw(PACKAGE_ID))
    return prepare_private_thought_script(script)


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
