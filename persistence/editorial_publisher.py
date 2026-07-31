from __future__ import annotations

import json
from typing import Any

from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.models import utc_now_iso


def publish_editorial_document(
    repository: GoogleSheetsEditorialRepository,
    document: dict[str, Any],
) -> bool:
    """Publica uma versão editorial e substitui somente o mesmo package_id.

    Retorna ``True`` quando houve publicação. Se a versão já estiver ativa, não
    grava novamente e evita consumo desnecessário da cota do Google Sheets.
    """

    package_id = str(document.get("package_id", "") or "").strip()
    script_version = str(document.get("script_version", "") or "").strip()
    if not package_id or not script_version:
        raise ValueError("package_id e script_version são obrigatórios.")

    current = repository.get_story(package_id)
    if current is not None and str(current.get("script_version", "")) == script_version:
        return False

    _validate_document(document)
    _delete_package_rows(repository, package_id)
    _append_document(repository, document)
    return True


def _validate_document(document: dict[str, Any]) -> None:
    blocks = document.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("O roteiro editorial precisa conter blocos.")

    beat_ids: set[str] = set()
    targets: set[str] = set()
    for block in blocks:
        if not isinstance(block, dict):
            raise ValueError("Bloco editorial inválido.")
        entry = str(block.get("entry_beat_id", "") or "").strip()
        if entry:
            targets.add(entry)
        for beat in block.get("beats", []):
            if not isinstance(beat, dict):
                raise ValueError("Beat editorial inválido.")
            beat_id = str(beat.get("beat_id", "") or "").strip()
            if not beat_id or beat_id in beat_ids:
                raise ValueError(f"beat_id ausente ou duplicado: {beat_id!r}")
            beat_ids.add(beat_id)
            next_beat = str(beat.get("next_beat_id", "") or "").strip()
            if next_beat:
                targets.add(next_beat)
            transitions = beat.get("allowed_transitions") or {}
            if isinstance(transitions, dict):
                targets.update(str(value) for value in transitions.values() if str(value).strip())

    missing = sorted(target for target in targets if target not in beat_ids)
    if missing:
        raise ValueError("Transições apontam para beats inexistentes: " + ", ".join(missing))


def _delete_package_rows(repository: GoogleSheetsEditorialRepository, package_id: str) -> None:
    for sheet_name in ("MEMORIES", "BEATS", "BLOCKS", "CHARACTERS", "STORIES"):
        worksheet = repository._worksheet(sheet_name)
        rows = worksheet.get_all_records(default_blank="")
        matching = [
            row_number
            for row_number, row in enumerate(rows, start=2)
            if str(row.get("package_id", "")).strip() == package_id
        ]
        for row_number in reversed(matching):
            worksheet.delete_rows(row_number)


def _append_document(repository: GoogleSheetsEditorialRepository, document: dict[str, Any]) -> None:
    now = utc_now_iso()
    package_id = str(document["package_id"])
    blocks = sorted(
        [dict(item) for item in document["blocks"]],
        key=lambda item: int(item.get("order", 0) or 0),
    )
    first_block = blocks[0]
    first_beat_id = str(first_block.get("entry_beat_id", ""))
    character = dict(document.get("character") or {})

    repository._append(
        "STORIES",
        {
            "package_id": package_id,
            "script_version": str(document["script_version"]),
            "title": str(document.get("title", "")),
            "introduction": str(document.get("introduction", "")),
            "character_id": str(character.get("character_id", "mary")),
            "first_block_id": str(first_block.get("block_id", "")),
            "first_beat_id": first_beat_id,
            "status": "active",
            "updated_at": now,
        },
    )
    repository._append(
        "CHARACTERS",
        {
            "package_id": package_id,
            "character_id": str(character.get("character_id", "mary")),
            "name": str(character.get("name", "Mary")),
            "age": int(character.get("age", 25) or 25),
            "physical_profile": _json(character.get("physical_profile") or []),
            "psychological_profile": _json(character.get("psychological_profile") or []),
            "speech_style": _json(character.get("speech_style") or []),
            "updated_at": now,
        },
    )

    global_rules = {
        "runtime_contract": document.get("runtime_contract") or {},
        "engagement_policy": document.get("engagement_policy") or {},
        "mary_state": document.get("mary_state") or {},
        "scene": {
            "scene_id": str(first_block.get("block_id", "")),
            "location": str(first_block.get("title", "")),
            "objective": str(document.get("introduction", "")),
        },
    }

    global_order = 0
    for block in blocks:
        repository._append(
            "BLOCKS",
            {
                "package_id": package_id,
                "block_id": str(block.get("block_id", "")),
                "order": int(block.get("order", 0) or 0),
                "title": str(block.get("title", "")),
                "entry_beat_id": str(block.get("entry_beat_id", "")),
                "max_movements_per_response": int(block.get("max_movements_per_response", 1) or 1),
                "max_questions_per_response": int(block.get("max_questions_per_response", 1) or 1),
                "rules_json": _json({**global_rules, "block_rules": block.get("rules") or []}),
                "updated_at": now,
            },
        )
        for beat in sorted(
            [dict(item) for item in block.get("beats", [])],
            key=lambda item: int(item.get("order", 0) or 0),
        ):
            global_order += 1
            beat_type = str(beat.get("type", "dialogue"))
            canonical_line = str(beat.get("canonical_line", ""))
            writes = [str(item) for item in beat.get("memory_writes", [])]
            if beat_type == "ending":
                ending_data = dict(beat.get("ending") or {})
                ending = {
                    "ending_id": str(beat.get("beat_id", "")),
                    "run_status": str(ending_data.get("run_status", "completed")),
                    "ending_code": str(ending_data.get("ending_code", beat.get("beat_id", ""))),
                    "visible_delivery": {"kind": "dialogue", "delivery": "guided", "text": canonical_line},
                    "memory_writes": writes,
                }
                required_json = ""
                ending_json = _json(ending)
            else:
                pilot_beat = {
                    "beat_id": str(beat.get("beat_id", "")),
                    "objective": str(beat.get("required_movement", "")),
                    "units": [
                        {
                            "unit_id": f"{beat.get('beat_id', '')}_canonical",
                            "kind": "dialogue",
                            "delivery": "anchored",
                            "anchor": canonical_line,
                            "instruction": str(beat.get("dramatic_direction", "")),
                        },
                        {"unit_id": f"{beat.get('beat_id', '')}_wait", "kind": "wait_user"},
                    ],
                    "on_user": beat.get("allowed_transitions") or {},
                }
                next_beat = str(beat.get("next_beat_id", "") or "")
                if next_beat and not pilot_beat["on_user"]:
                    pilot_beat["on_user"] = {"engaged": next_beat}
                required_json = _json(pilot_beat)
                ending_json = ""

            repository._append(
                "BEATS",
                {
                    "package_id": package_id,
                    "beat_id": str(beat.get("beat_id", "")),
                    "block_id": str(block.get("block_id", "")),
                    "order": global_order,
                    "type": beat_type,
                    "required_movement": required_json,
                    "canonical_line": canonical_line,
                    "dramatic_direction": str(beat.get("dramatic_direction", "")),
                    "next_beat_id": str(beat.get("next_beat_id", "")),
                    "max_questions": int(beat.get("max_questions", 1) or 0),
                    "max_sentences": int(beat.get("max_sentences", 1) or 1),
                    "memory_writes_json": _json(writes),
                    "allowed_transitions_json": _json(beat.get("allowed_transitions") or {}),
                    "ending_json": ending_json,
                    "status": str(beat.get("status", "active")),
                    "updated_at": now,
                },
            )

    for memory in document.get("memories", []):
        if not isinstance(memory, dict):
            continue
        repository._append(
            "MEMORIES",
            {
                "package_id": package_id,
                "memory_id": str(memory.get("memory_id", "")),
                "memory_text": str(memory.get("memory_text", "")),
                "source_beat_id": str(memory.get("source_beat_id", "")),
                "status": "active",
                "updated_at": now,
            },
        )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
