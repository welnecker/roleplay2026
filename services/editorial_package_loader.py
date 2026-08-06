from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from packages.models import InstalledStoryPackage
from services.editorial_compiler import compile_editorial_document
from services.editorial_progression import prepare_editorial_script
from services.editorial_runtime import EditorialScript
from services.narrative_context import validate_memory_references, validate_terminal_yards


class EditorialPackageError(RuntimeError):
    pass


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


def _package_file(package: InstalledStoryPackage, relative_path: str) -> Path:
    root = package.root.resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise EditorialPackageError(f"Arquivo editorial fora da pasta do pacote: {relative_path}")
    if not target.is_file():
        raise EditorialPackageError(f"Arquivo editorial inexistente: {target}")
    return target


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


def load_editorial_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(_protect_editorial_plain_scalars(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise EditorialPackageError(f"Não foi possível ler {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise EditorialPackageError(f"Documento editorial inválido: {path}")
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


def _append_unique_strings(target: dict[str, Any], key: str, values: Any) -> None:
    if not isinstance(values, list):
        raise EditorialPackageError(f"{key}.append deve ser uma lista")
    current = [str(item).strip() for item in target.get(key, []) or [] if str(item).strip()]
    for item in values:
        text = str(item).strip()
        if text and text not in current:
            current.append(text)
    target[key] = current


def _merge_character_patch(merged: dict[str, Any], extension: dict[str, Any]) -> None:
    patch = extension.get("character_patch")
    if patch is None:
        return
    if not isinstance(patch, dict):
        raise EditorialPackageError("character_patch deve ser um mapa")
    character = merged.setdefault("character", {})
    if not isinstance(character, dict):
        raise EditorialPackageError("character deve ser um mapa")
    for profile_key in ("physical_profile", "psychological_profile", "speech_style"):
        profile_patch = patch.get(profile_key)
        if profile_patch is None:
            continue
        if not isinstance(profile_patch, dict):
            raise EditorialPackageError(f"character_patch.{profile_key} deve ser um mapa")
        _append_unique_strings(character, profile_key, profile_patch.get("append", []))


def _replace_declared_policy(
    merged: dict[str, Any],
    extension: dict[str, Any],
    key: str,
) -> None:
    value = extension.get(key)
    if value is None:
        return
    if not isinstance(value, dict):
        raise EditorialPackageError(f"{key} deve ser um mapa")
    merged[key] = deepcopy(value)


def merge_editorial_extension(document: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(document)
    beats_by_id = {
        str(beat.get("beat_id", "")): beat
        for beat in _iter_beats(merged)
        if str(beat.get("beat_id", "")).strip()
    }

    for beat_id, patch in dict(extension.get("patch_beats") or {}).items():
        target = beats_by_id.get(str(beat_id))
        if target is None:
            raise EditorialPackageError(f"Beat a atualizar não encontrado: {beat_id}")
        if not isinstance(patch, dict):
            raise EditorialPackageError(f"Patch inválido para o beat {beat_id}")
        target.update(deepcopy(patch))

    append_blocks = extension.get("append_blocks") or []
    if not isinstance(append_blocks, list):
        raise EditorialPackageError("append_blocks deve ser uma lista")
    merged.setdefault("blocks", []).extend(deepcopy(append_blocks))

    organic_slack = extension.get("organic_slack")
    if organic_slack is not None:
        if not isinstance(organic_slack, dict):
            raise EditorialPackageError("organic_slack deve ser um mapa")
        merged["organic_slack"] = deepcopy(organic_slack)

    _replace_declared_policy(merged, extension, "bridge_policy")
    _replace_declared_policy(merged, extension, "runtime_policy")

    _merge_character_patch(merged, extension)

    incoming_memories = _memory_entries(extension.get("memories"))
    if incoming_memories:
        existing_memories = _memory_entries(merged.get("memories"))
        known_ids = {str(item.get("memory_id", "")) for item in existing_memories}
        for definition in incoming_memories:
            memory_id = str(definition.get("memory_id", ""))
            if not memory_id:
                raise EditorialPackageError("Memória sem memory_id")
            if memory_id in known_ids:
                raise EditorialPackageError(f"Memória duplicada: {memory_id}")
            known_ids.add(memory_id)
            existing_memories.append(definition)
        merged["memories"] = existing_memories

    return merged


def load_editorial_document(package: InstalledStoryPackage) -> dict[str, Any]:
    runtime = package.manifest.runtime
    if runtime.kind != "editorial" or runtime.editorial is None:
        raise EditorialPackageError(
            f"Pacote {package.manifest.package_id!r} não declara runtime editorial"
        )

    document = load_editorial_yaml(_package_file(package, runtime.editorial.source))
    for relative_path in runtime.editorial.extensions:
        extension = load_editorial_yaml(_package_file(package, relative_path))
        document = merge_editorial_extension(document, extension)

    package_id = str(document.get("package_id", "") or "").strip()
    if package_id and package_id != package.manifest.package_id:
        raise EditorialPackageError(
            "package_id do documento editorial difere do manifesto: "
            f"{package_id!r} != {package.manifest.package_id!r}"
        )

    validate_memory_references(document)
    validate_terminal_yards(document)
    return document


def compile_editorial_package(package: InstalledStoryPackage) -> EditorialScript:
    document = load_editorial_document(package)
    return prepare_editorial_script(EditorialScript(compile_editorial_document(document)))


def editorial_story_start(package: InstalledStoryPackage) -> tuple[str, str, str]:
    raw = load_editorial_document(package)
    blocks = [item for item in raw.get("blocks", []) if isinstance(item, dict)]
    if not blocks:
        raise EditorialPackageError("História editorial sem blocos")
    first = min(blocks, key=lambda item: int(item.get("order", 0) or 0))
    return (
        str(raw.get("script_version", "")),
        str(first.get("block_id", "")),
        str(first.get("entry_beat_id", "")),
    )
