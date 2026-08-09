from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from typing import Any, Iterable


_MARKER = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$", re.DOTALL)
_FIRST_PERSON = re.compile(
    r"\b(eu|me|mim|meu|minha|meus|minhas|comigo|estou|sou|vou|quero|"
    r"preciso|sinto|penso|percebo|acho|espero|posso|tenho|sei|fico)\b",
    re.IGNORECASE,
)


class SpreadsheetStoryError(ValueError):
    pass


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold()


def _marker(value: Any) -> tuple[str, str, str]:
    raw = str(value or "").strip()
    match = _MARKER.match(raw)
    if match is None:
        raise SpreadsheetStoryError(f"Instrução sem marcador: {raw!r}")
    header = match.group(1).strip()
    text = match.group(2).strip()
    parts = header.split(maxsplit=1)
    kind = _plain(parts[0]).upper()
    argument = parts[1].strip() if len(parts) > 1 else ""
    if kind == "FALA" and _plain(argument) in {"exata", "livre"}:
        kind = "FALA_" + _plain(argument).upper()
        argument = ""
    if kind == "PATIO" and _plain(argument).startswith("final"):
        kind = "PATIO_FINAL"
        argument = argument[5:].strip()
    return kind, argument, text


def _active_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        dict(row)
        for row in rows
        if str(row.get("status", "active") or "active").strip().casefold() == "active"
    ]
    selected.sort(key=lambda row: (int(row.get("order", 0) or 0), str(row.get("line_id", ""))))
    return selected


def _validate_first_person(kind: str, text: str, *, line_id: str, character_name: str) -> None:
    if kind not in {"BEAT", "PENSAMENTO", "PONTE", "PATIO_FINAL"} or not text:
        return
    if character_name and re.search(rf"\b{re.escape(character_name)}\b", text, re.IGNORECASE):
        raise SpreadsheetStoryError(
            f"{line_id}: use primeira pessoa; não escreva o nome da personagem."
        )
    if kind in {"BEAT", "PONTE", "PATIO_FINAL"} and not _FIRST_PERSON.search(text):
        raise SpreadsheetStoryError(
            f"{line_id}: {kind} deve ser escrito em primeira pessoa."
        )


def compile_spreadsheet_story(
    base_document: dict[str, Any],
    rows: Iterable[dict[str, Any]],
    *,
    script_version: str,
) -> dict[str, Any]:
    """Compila as linhas autorais de ROTEIROS para o documento editorial atual."""

    source_rows = _active_rows(rows)
    if not source_rows:
        raise SpreadsheetStoryError("ROTEIROS não possui linhas ativas.")

    document = deepcopy(base_document)
    document["script_version"] = str(script_version or document.get("script_version", ""))
    document["blocks"] = []

    character = dict(document.get("character") or {})
    character_name = str(character.get("name", "") or "").strip()
    blocks: list[dict[str, Any]] = document["blocks"]
    current_block: dict[str, Any] | None = None
    current_beat: dict[str, Any] | None = None
    pending_transition = ""
    final_yard = False
    endings: list[dict[str, Any]] = []
    seen_line_ids: set[str] = set()

    def ensure_block() -> dict[str, Any]:
        nonlocal current_block
        if current_block is None:
            current_block = {
                "block_id": "roteiro",
                "order": 1,
                "title": "Roteiro",
                "entry_beat_id": "",
                "max_movements_per_response": 1,
                "max_questions_per_response": 1,
                "rules": [],
                "beats": [],
            }
            blocks.append(current_block)
        return current_block

    def flush_beat() -> None:
        nonlocal current_beat
        if current_beat is None:
            return
        thought = str(current_beat.pop("_thought", "") or "").strip()
        speech = str(current_beat.pop("_speech", "") or "").strip()
        transition = str(current_beat.pop("_transition", "") or "").strip()
        visible: list[str] = []
        if transition:
            visible.append(f"[{transition.upper()}]")
        if thought:
            visible.append(f"[PENSAMENTO]\n{thought}\n[/PENSAMENTO]")
        if speech:
            visible.append(speech)
        current_beat["canonical_line"] = "\n\n".join(visible)
        current_beat = None

    for row in source_rows:
        line_id = str(row.get("line_id", "") or "").strip()
        if not line_id or line_id in seen_line_ids:
            raise SpreadsheetStoryError(f"line_id ausente ou duplicado: {line_id!r}")
        seen_line_ids.add(line_id)
        kind, argument, text = _marker(row.get("instruction"))
        _validate_first_person(
            kind,
            text,
            line_id=line_id,
            character_name=character_name,
        )

        if kind == "CENA":
            flush_beat()
            scene_id = argument or line_id
            current_block = {
                "block_id": scene_id,
                "order": len(blocks) + 1,
                "title": text or scene_id.replace("_", " ").title(),
                "entry_beat_id": "",
                "max_movements_per_response": 1,
                "max_questions_per_response": 1,
                "rules": [],
                "beats": [],
            }
            if final_yard:
                current_block.update(
                    {
                        "block_type": "terminal_yard",
                        "min_user_turns": 2,
                        "max_user_turns": 6,
                    }
                )
            blocks.append(current_block)
            continue

        if kind == "TRANSICAO":
            flush_beat()
            pending_transition = text or argument
            continue

        if kind == "PATIO_FINAL":
            flush_beat()
            final_yard = True
            current_block = {
                "block_id": argument or "patio_final",
                "block_type": "terminal_yard",
                "order": len(blocks) + 1,
                "title": text or "Pátio final",
                "entry_beat_id": "",
                "min_user_turns": 2,
                "max_user_turns": 6,
                "max_movements_per_response": 1,
                "max_questions_per_response": 1,
                "rules": ["Eu desacelero a história antes do encerramento."],
                "beats": [],
            }
            blocks.append(current_block)
            continue

        if kind == "BEAT":
            flush_beat()
            block = ensure_block()
            current_beat = {
                "beat_id": line_id,
                "order": len(block["beats"]) + 1,
                "type": "dialogue",
                "required_movement": text,
                "dramatic_direction": "",
                "next_beat_id": "",
                "max_questions": 1,
                "max_sentences": 4,
                "memory_writes": [],
                "allowed_transitions": {},
                "status": "active",
                "_thought": "",
                "_speech": "",
                "_transition": pending_transition,
            }
            pending_transition = ""
            block["beats"].append(current_beat)
            if not block["entry_beat_id"]:
                block["entry_beat_id"] = line_id
            continue

        if kind in {"PENSAMENTO", "FALA", "FALA_EXATA", "FALA_LIVRE", "PONTE"}:
            if current_beat is None:
                raise SpreadsheetStoryError(f"{line_id}: {kind} sem [BEAT] anterior.")
            if kind == "PENSAMENTO":
                current_beat["_thought"] = "\n".join(
                    part for part in (current_beat["_thought"], text) if part
                )
            elif kind in {"FALA", "FALA_EXATA"}:
                current_beat["_speech"] = "\n".join(
                    part for part in (current_beat["_speech"], text) if part
                )
            elif kind == "FALA_LIVRE":
                direction = f"Crie em primeira pessoa a fala orientada por: {text}"
                current_beat["dramatic_direction"] = "\n".join(
                    part for part in (current_beat["dramatic_direction"], direction) if part
                )
            else:
                current_beat["dramatic_direction"] = "\n".join(
                    part
                    for part in (
                        current_beat["dramatic_direction"],
                        f"PONTE: {text}",
                    )
                    if part
                )
            continue

        if kind == "FIM":
            flush_beat()
            block = ensure_block()
            ending = {
                "beat_id": line_id,
                "order": len(block["beats"]) + 1,
                "type": "ending",
                "required_movement": text,
                "canonical_line": "",
                "dramatic_direction": "",
                "next_beat_id": "",
                "max_questions": 0,
                "max_sentences": 1,
                "memory_writes": [],
                "allowed_transitions": {},
                "ending": {
                    "run_status": "completed",
                    "ending_code": argument or "story_complete",
                },
                "status": "active",
            }
            block["beats"].append(ending)
            endings.append(ending)
            continue

        raise SpreadsheetStoryError(f"{line_id}: marcador não reconhecido: {kind}")

    flush_beat()
    blocks[:] = [block for block in blocks if block.get("beats")]
    blocks.sort(
        key=lambda block: (
            not bool(str(block.get("entry_beat_id", "") or "").strip()),
            int(block.get("order", 0) or 0),
        )
    )
    for block_order, block in enumerate(blocks, start=1):
        block["order"] = block_order
    if not blocks or not any(block.get("beats") for block in blocks):
        raise SpreadsheetStoryError("O roteiro não contém beats.")
    if not endings:
        raise SpreadsheetStoryError("O roteiro precisa terminar com [FIM].")

    ordered_beats = [
        beat
        for block in blocks
        for beat in block.get("beats", [])
        if str(beat.get("type", "dialogue")) != "ending"
    ]
    ending_id = str(endings[-1]["beat_id"])
    for index, beat in enumerate(ordered_beats):
        target = (
            str(ordered_beats[index + 1]["beat_id"])
            if index + 1 < len(ordered_beats)
            else ending_id
        )
        beat["next_beat_id"] = target
        beat["allowed_transitions"] = {
            "engaged": target,
            "minimal": target,
            "dismissive": beat["beat_id"],
            "nonsense": beat["beat_id"],
            "mocking": ending_id,
            "hostile": ending_id,
        }

    return document


__all__ = ["SpreadsheetStoryError", "compile_spreadsheet_story"]
