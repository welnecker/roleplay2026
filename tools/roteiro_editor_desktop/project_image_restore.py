from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


def _existing_path(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    path = Path(raw)
    if path.exists() and path.is_file():
        return str(path)
    return ""


def restore_project_image_state(
    payload: dict[str, Any],
    *,
    project_path: Path,
) -> dict[str, Any]:
    """Reidrata imagens de projetos salvos, inclusive exports e formatos antigos."""

    restored = deepcopy(payload)
    project_dir = project_path.resolve().parent

    raw_sources = restored.get("image_sources") or {}
    if not isinstance(raw_sources, dict):
        raw_sources = {}

    raw_map = restored.get("image_map") or {}
    if not isinstance(raw_map, dict):
        raw_map = {}

    raw_origins = restored.get("assigned_reference_origins") or {}
    if not isinstance(raw_origins, dict):
        raw_origins = {}
    assigned_reference_origins = {
        str(image_id): str(origin)
        for image_id, origin in raw_origins.items()
        if str(image_id or "").strip() and str(origin or "").strip()
    }
    restored["assigned_reference_origins"] = assigned_reference_origins

    image_ids: list[str] = []
    for value in raw_map.values():
        image_id = str(value or "").strip()
        if image_id and image_id not in image_ids:
            image_ids.append(image_id)
    for image_id in raw_sources:
        clean = str(image_id or "").strip()
        if clean and clean not in image_ids:
            image_ids.append(clean)

    resolved_sources: dict[str, str] = {}
    for image_id in image_ids:
        original = _existing_path(raw_sources.get(image_id, ""))
        if original:
            resolved_sources[image_id] = original
            continue

        candidates = (
            project_dir / "imagens" / image_id,
            project_dir / image_id,
            project_dir / f"{project_path.stem}_assets" / image_id,
        )
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                resolved_sources[image_id] = str(candidate)
                break

    restored["image_sources"] = resolved_sources

    # Projetos novos guardam a origem das referências que foram fisicamente
    # movidas para ``_atribuidas``. Essas imagens precisam continuar disponíveis
    # para exportação, mas não devem reaparecer na galeria de imagens livres.
    assigned_sources = {
        source
        for image_id, source in resolved_sources.items()
        if image_id in assigned_reference_origins
    }

    references: list[str] = []
    raw_references = restored.get("reference_files") or []
    if isinstance(raw_references, (list, tuple)):
        for value in raw_references:
            existing = _existing_path(value)
            if (
                existing
                and existing not in assigned_sources
                and existing not in references
            ):
                references.append(existing)

    # Mantém o comportamento de recuperação de projetos antigos/exportados.
    # Para o novo formato, fontes gerenciadas como "atribuídas" ficam fora.
    for image_id, source in resolved_sources.items():
        if image_id in assigned_reference_origins:
            continue
        if source not in references:
            references.append(source)
    restored["reference_files"] = references

    raw_index = restored.get("reference_index", -1)
    try:
        reference_index = int(raw_index)
    except Exception:
        reference_index = -1
    if references:
        restored["reference_index"] = max(0, min(len(references) - 1, reference_index))
    else:
        restored["reference_index"] = -1

    bindings = restored.get("description_bindings") or {}
    if isinstance(bindings, dict):
        normalized_bindings: dict[str, dict[str, str]] = {}
        for key, value in bindings.items():
            if not isinstance(value, dict):
                continue
            binding = {str(k): str(v) for k, v in value.items()}
            image_id = str(binding.get("image_id", "") or "").strip()
            if image_id and image_id in resolved_sources:
                binding["source"] = resolved_sources[image_id]
            normalized_bindings[str(key)] = binding
        restored["description_bindings"] = normalized_bindings

    return restored


__all__ = ["restore_project_image_state"]
