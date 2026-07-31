from __future__ import annotations

import json
import time
from typing import Any

from gspread.exceptions import APIError

from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.models import utc_now_iso

_SHEETS = ("CHARACTERS", "BLOCKS", "BEATS", "MEMORIES", "STORIES")


def publish_editorial_document(
    repository: GoogleSheetsEditorialRepository,
    document: dict[str, Any],
) -> bool:
    """Publica uma versão editorial com poucas escritas no Google Sheets.

    Cada aba é reconstruída em memória, preservando outras histórias, e gravada
    de uma só vez. ``STORIES`` é escrita por último e funciona como confirmação
    da publicação. Uma carga parcial é detectada pelas contagens esperadas.
    """

    package_id = str(document.get("package_id", "") or "").strip()
    script_version = str(document.get("script_version", "") or "").strip()
    if not package_id or not script_version:
        raise ValueError("package_id e script_version são obrigatórios.")

    _validate_document(document)
    rows_by_sheet = _build_rows(document)

    current = repository.get_story(package_id)
    if (
        current is not None
        and str(current.get("script_version", "")) == script_version
        and _publication_is_complete(repository, package_id, rows_by_sheet)
    ):
        return False

    # A confirmação em STORIES é sempre a última escrita. Se houver falha antes,
    # a próxima execução detectará a carga incompleta e tentará novamente.
    for sheet_name in _SHEETS:
        _replace_package_rows(
            repository,
            sheet_name=sheet_name,
            package_id=package_id,
            new_rows=rows_by_sheet[sheet_name],
        )
    return True


def _publication_is_complete(
    repository: GoogleSheetsEditorialRepository,
    package_id: str,
    rows_by_sheet: dict[str, list[dict[str, Any]]],
) -> bool:
    for sheet_name, expected_rows in rows_by_sheet.items():
        actual = sum(
            1
            for row in repository._records(sheet_name)
            if str(row.get("package_id", "")).strip() == package_id
        )
        if actual != len(expected_rows):
            return False
    return True


def _replace_package_rows(
    repository: GoogleSheetsEditorialRepository,
    *,
    sheet_name: str,
    package_id: str,
    new_rows: list[dict[str, Any]],
) -> None:
    worksheet = repository._worksheet(sheet_name)
    headers = [str(value).strip() for value in worksheet.row_values(1)]
    if not headers:
        raise RuntimeError(f"A aba {sheet_name} não possui cabeçalhos.")

    package_index = headers.index("package_id")
    existing_values = worksheet.get_all_values()
    kept_rows: list[list[Any]] = []
    for row in existing_values[1:]:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        if str(padded[package_index]).strip() != package_id:
            kept_rows.append(padded[: len(headers)])

    matrix: list[list[Any]] = [headers, *kept_rows]
    matrix.extend(
        [[row.get(header, "") for header in headers] for row in new_rows]
    )

    _with_quota_retry(worksheet.clear)
    _with_quota_retry(
        lambda: worksheet.update(
            values=matrix,
            range_name="A1",
            value_input_option="RAW",
        )
    )


def _with_quota_retry(operation: Any) -> Any:
    delays = (10, 20, 30)
    for attempt in range(len(delays) + 1):
        try:
            return operation()
        except APIError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            is_quota = status == 429 or "429" in str(exc) or "Quota exceeded" in str(exc)
            if not is_quota or attempt >= len(delays):
                raise
            time.sleep(delays[attempt])
    raise RuntimeError("Falha inesperada ao gravar no Google Sheets.")


def _build_rows(document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    now = utc_now_iso()
    package_id = str(document["package_id"])
    blocks = sorted(
        [dict(item) for item in document["blocks"]],
        key=lambda item: int(item.get("order", 0) or 0),
    )
    first_block = blocks[0]
    character = dict(document.get("character") or {})

    result: dict[str, list[dict[str, Any]]] = {name: [] for name in _SHEETS}
    result["STORIES"].append(
        {
            "package_id": package_id,
            "script_version": str(document["script_version"]),
            "title": str(document.get("title", "")),
            "introduction": str(document.get("introduction", "")),
            "character_id": str(character.get("character_id", "mary")),
            "first_block_id": str(first_block.get("block_id", "")),
            "first_beat_id": str(first_block.get("entry_beat_id", "")),
            "status": "active",
            "updated_at": now,
        }
    )
    result["CHARACTERS"].append(
        {
            "package_id": package_id,
            "character_id": str(character.get("character_id", "mary")),
            "name": str(character.get("name", "Mary")),
            "age": int(character.get("age", 25) or 25),
            "physical_profile": _json(character.get("physical_profile") or []),
            "psychological_profile": _json(character.get("psychological_profile") or []),
            "speech_style": _json(character.get("speech_style") or []),
            "updated_at": now,
        }
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
        block_id = str(block.get("block_id", ""))
        result["BLOCKS"].append(
            {
                "package_id": package_id,
                "block_id": block_id,
                "order": int(block.get("order", 0) or 0),
                "title": str(block.get("title", "")),
                "entry_beat_id": str(block.get("entry_beat_id", "")),
                "max_movements_per_response": int(block.get("max_movements_per_response", 1) or 1),
                "max_questions_per_response": int(block.get("max_questions_per_response", 1) or 1),
                "rules_json": _json({**global_rules, "block_rules": block.get("rules") or []}),
                "updated_at": now,
            }
        )
        for beat in sorted(
            [dict(item) for item in block.get("beats", [])],
            key=lambda item: int(item.get("order", 0) or 0),
        ):
            global_order += 1
            result["BEATS"].append(
                _beat_row(
                    package_id=package_id,
                    block_id=block_id,
                    global_order=global_order,
                    beat=beat,
                    now=now,
                )
            )

    for memory in document.get("memories", []):
        if isinstance(memory, dict):
            result["MEMORIES"].append(
                {
                    "package_id": package_id,
                    "memory_id": str(memory.get("memory_id", "")),
                    "memory_text": str(memory.get("memory_text", "")),
                    "source_beat_id": str(memory.get("source_beat_id", "")),
                    "status": "active",
                    "updated_at": now,
                }
            )
    return result


def _beat_row(
    *,
    package_id: str,
    block_id: str,
    global_order: int,
    beat: dict[str, Any],
    now: str,
) -> dict[str, Any]:
    beat_id = str(beat.get("beat_id", ""))
    beat_type = str(beat.get("type", "dialogue"))
    canonical_line = str(beat.get("canonical_line", ""))
    writes = [str(item) for item in beat.get("memory_writes", [])]

    if beat_type == "ending":
        ending_data = dict(beat.get("ending") or {})
        ending_json = _json(
            {
                "ending_id": beat_id,
                "run_status": str(ending_data.get("run_status", "completed")),
                "ending_code": str(ending_data.get("ending_code", beat_id)),
                "visible_delivery": {
                    "kind": "dialogue",
                    "delivery": "guided",
                    "text": canonical_line,
                },
                "memory_writes": writes,
            }
        )
        required_json = ""
    else:
        transitions = beat.get("allowed_transitions") or {}
        next_beat = str(beat.get("next_beat_id", "") or "")
        if next_beat and not transitions:
            transitions = {"engaged": next_beat}
        required_json = _json(
            {
                "beat_id": beat_id,
                "objective": str(beat.get("required_movement", "")),
                "units": [
                    {
                        "unit_id": f"{beat_id}_canonical",
                        "kind": "dialogue",
                        "delivery": "anchored",
                        "anchor": canonical_line,
                        "instruction": str(beat.get("dramatic_direction", "")),
                    },
                    {"unit_id": f"{beat_id}_wait", "kind": "wait_user"},
                ],
                "on_user": transitions,
            }
        )
        ending_json = ""

    return {
        "package_id": package_id,
        "beat_id": beat_id,
        "block_id": block_id,
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
    }


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


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
