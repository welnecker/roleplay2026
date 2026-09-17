from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from services import novel_frame_patch


def clean_image_id(value: object) -> str:
    return str(value or "").strip().replace("\\", "/")


def _row_media_maps(
    rows: Iterable[dict[str, Any]],
    column: str,
) -> tuple[dict[str, str], dict[str, str]]:
    line_media: dict[str, str] = {}
    frame_media: dict[str, str] = {}
    description_index = 0
    for raw in rows:
        row = dict(raw)
        if str(row.get("status", "active") or "active").strip().casefold() != "active":
            continue
        line_id = str(row.get("line_id", "") or "").strip()
        kind, _actor, _body = novel_frame_patch._tag(row.get("instruction"))
        if kind == "descricao":
            description_index += 1
        media_id = clean_image_id(row.get(column))
        if not line_id or not media_id:
            continue
        line_media[line_id] = media_id
        if kind == "descricao":
            frame_media[
                novel_frame_patch._frame_id_from_description(
                    line_id,
                    description_index,
                )
            ] = media_id
    return line_media, frame_media


def enrich_compiled_document_with_media_ids(
    document: dict[str, Any],
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Copia os IDs autorais de imagem, movimento e áudio para o quadro V2."""

    materialized = [dict(row) for row in rows]
    media_maps = {
        field: _row_media_maps(materialized, field)
        for field in ("image_id", "motion_id", "audio_id")
    }
    if not any(line or frame for line, frame in media_maps.values()):
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
            for field, (_line_media, frame_media) in media_maps.items():
                frame_value = frame_media.get(current_frame_id, "")
                if frame_value:
                    frame[field] = frame_value
            for entry in frame.get("entries", []) or []:
                if not isinstance(entry, dict):
                    continue
                line_id = str(entry.get("line_id", "") or "").strip()
                for field, (line_media, _frame_media) in media_maps.items():
                    entry_value = line_media.get(line_id, "")
                    if entry_value:
                        entry[field] = entry_value
            beat["required_movement"] = prefix + json.dumps(
                frame,
                ensure_ascii=False,
                separators=(",", ":"),
            )
    return enriched


def enrich_compiled_document_with_image_ids(
    document: dict[str, Any],
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Compatibilidade pública para consumidores do nome histórico."""

    return enrich_compiled_document_with_media_ids(document, rows)


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


def explicit_media_for_frame(
    frame: Mapping[str, object],
    field: str,
) -> tuple[str, tuple[str, ...]]:
    """Retorna mídia sem herança: cada movimento/áudio pertence à sua linha."""

    base = clean_image_id(frame.get(field))
    entries = tuple(
        clean_image_id(raw.get(field)) if isinstance(raw, Mapping) else ""
        for raw in frame.get("entries", []) or []
    )
    return base, entries


__all__ = [
    "clean_image_id",
    "enrich_compiled_document_with_image_ids",
    "enrich_compiled_document_with_media_ids",
    "explicit_media_for_frame",
    "image_sequence_for_frame",
]
