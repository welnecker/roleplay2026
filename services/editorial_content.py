from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.editorial_publisher import publish_editorial_document
from persistence.spreadsheet_config import read_spreadsheet_ids
import services.pilot_supermarket as pilot_supermarket_module
from services.editorial_compiler import compile_editorial_document
from services.narrative_context import validate_memory_references, validate_terminal_yards
from services.pilot_supermarket import PilotScript
from services.supermarket_script_v2 import (
    clean_supermarket_script_v2_response,
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)


PACKAGE_ID = "roleplay2026.casada_frustrada"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "installed_stories" / "casada_frustrada"
EDITORIAL_PATH = PACKAGE_ROOT / "supermarket_pilot.yaml"
EXTENSION_PATHS = (
    PACKAGE_ROOT / "supermarket_continuation.yaml",
    PACKAGE_ROOT / "narrative_enhancements.yaml",
    PACKAGE_ROOT / "full_story.yaml",
)
_EDITORIAL_REPOSITORY: GoogleSheetsEditorialRepository | None = None
_EDITORIAL_READY = False
_FREE_TEXT_KEYS = {
    "introduction",
    "title",
    "required_movement",
    "canonical_line",
    "dramatic_direction",
    "text",
    "summary",
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
        raise ValueError("Documento editorial YAML inválido.")
    return raw


def _iter_beats(document: dict[str, Any]):
    for block in document.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []) or []:
            if isinstance(beat, dict):
                yield beat


def _memory_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [deepcopy(item) for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [
            {
                "memory_id": str(memory_id),
                "memory_text": str(definition.get("summary") or definition.get("memory_text") or ""),
                "summary": str(definition.get("summary") or definition.get("memory_text") or ""),
                "category": str(definition.get("category", "event") or "event"),
                "importance": int(definition.get("importance", 5) or 5),
                "source_beat_id": str(definition.get("source_beat_id", "")),
            }
            for memory_id, definition in value.items()
            if isinstance(definition, dict)
        ]
    return []


def _merge_extension(document: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(document)
    beats_by_id = {
        str(beat.get("beat_id", "")): beat
        for beat in _iter_beats(merged)
        if str(beat.get("beat_id", "")).strip()
    }

    for beat_id, patch in dict(extension.get("patch_beats") or {}).items():
        target = beats_by_id.get(str(beat_id))
        if target is None:
            raise ValueError(f"Beat a atualizar não encontrado: {beat_id}")
        if not isinstance(patch, dict):
            raise ValueError(f"Patch inválido para o beat {beat_id}")
        target.update(deepcopy(patch))

    append_blocks = extension.get("append_blocks") or []
    if not isinstance(append_blocks, list):
        raise ValueError("append_blocks deve ser uma lista.")
    merged.setdefault("blocks", []).extend(deepcopy(append_blocks))

    incoming_memories = _memory_entries(extension.get("memories"))
    if incoming_memories:
        existing_memories = _memory_entries(merged.get("memories"))
        known_ids = {str(item.get("memory_id", "")) for item in existing_memories}
        for definition in incoming_memories:
            memory_id = str(definition.get("memory_id", ""))
            if not memory_id:
                raise ValueError("Memória sem memory_id.")
            if memory_id in known_ids:
                raise ValueError(f"Memória duplicada: {memory_id}")
            known_ids.add(memory_id)
            existing_memories.append(definition)
        merged["memories"] = existing_memories

    return merged


def load_source_document() -> dict[str, Any]:
    document = load_editorial_yaml_text(EDITORIAL_PATH.read_text(encoding="utf-8"))
    for path in EXTENSION_PATHS:
        if not path.is_file():
            continue
        extension = load_editorial_yaml_text(path.read_text(encoding="utf-8"))
        document = _merge_extension(document, extension)
    validate_memory_references(document)
    validate_terminal_yards(document)
    return document


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
    """Carrega a fonte única e adapta somente sua estrutura ao motor."""

    ensure_editorial_pilot(secrets)
    compiled = compile_editorial_document(load_source_document())
    return prepare_supermarket_script_v2(PilotScript(compiled))


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
