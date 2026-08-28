from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from services import novel_frame_patch


def clean_image_id(value: object) -> str:
    return str(value or "").strip().replace("\\", "/")


def _row_image_maps(
    rows: Iterable[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    line_images: dict[str, str] = {}
    frame_images: dict[str, str] = {}
    description_index = 0
    for raw in rows:
        row = dict(raw)
        if str(row.get("status", "active") or "active").strip().casefold() != "active":
            continue
        line_id = str(row.get("line_id", "") or "").strip()
        kind, _actor, _body = novel_frame_patch._tag(row.get("instruction"))
        if kind == "descricao":
            description_index += 1
        image_id = clean_image_id(row.get("image_id"))
        if not line_id or not image_id:
            continue
        line_images[line_id] = image_id
        if kind == "descricao":
            frame_images[
                novel_frame_patch._frame_id_from_description(
                    line_id,
                    description_index,
                )
            ] = image_id
    return line_images, frame_images


def enrich_compiled_document_with_image_ids(
    document: dict[str, Any],
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Copia ``image_id`` autoral para o payload V2 compilado."""

    materialized = [dict(row) for row in rows]
    line_images, frame_images = _row_image_maps(materialized)
    if not line_images and not frame_images:
        return document

    enriched = deepcopy(document)
    prefix = novel_frame_patch._FRAME_PREFIX
    for block in enriched.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []) or []:
            if not isinstance(beat, dict):
                continue
            movement = str(beat.get("required_movement", "") or "")
            if not movement.startswith(prefix):
                continue
            try:
                frame = json.loads(movement[len(prefix) :])
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(frame, dict):
                continue
            current_frame_id = str(frame.get("frame_id", "") or "").strip()
            frame_image = frame_images.get(current_frame_id, "")
            if frame_image:
                frame["image_id"] = frame_image
            for entry in frame.get("entries", []) or []:
                if not isinstance(entry, dict):
                    continue
                entry_image = line_images.get(
                    str(entry.get("line_id", "") or "").strip(),
                    "",
                )
                if entry_image:
                    entry["image_id"] = entry_image
            beat["required_movement"] = prefix + json.dumps(
                frame,
                ensure_ascii=False,
                separators=(",", ":"),
            )
    return enriched


def image_sequence_for_frame(
    frame: Mapping[str, object],
    *,
    inherited_image_id: str = "",
) -> tuple[str, tuple[str, ...]]:
    """Retorna imagem-base e imagem efetiva de cada entry com carry-forward."""

    last = clean_image_id(frame.get("image_id")) or clean_image_id(inherited_image_id)
    base = last
    result: list[str] = []
    for raw in frame.get("entries", []) or []:
        entry = raw if isinstance(raw, Mapping) else {}
        own = clean_image_id(entry.get("image_id"))
        if own:
            last = own
        result.append(last)
    return base, tuple(result)


__all__ = [
    "clean_image_id",
    "enrich_compiled_document_with_image_ids",
    "image_sequence_for_frame",
]
