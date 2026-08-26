from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from services.script_authoring import (
    ROTEIROS_COLUMNS,
    ScriptAuthoringError,
    rows_to_csv,
    rows_to_tsv,
    slugify,
)


_TAG_PATTERN = re.compile(
    r"(?ms)^[ \t]*\[([^\]\n]+)\][ \t]*(.*?)(?=^[ \t]*\[[^\]\n]+\]|\Z)"
)


@dataclass(frozen=True, slots=True)
class V2Instruction:
    kind: str
    actor: str
    text: str
    instruction: str
    delivery: str = "adaptavel"


@dataclass(frozen=True, slots=True)
class V2PreviewEntry:
    kind: str
    actor: str
    text: str
    delivery: str = "adaptavel"


@dataclass(frozen=True, slots=True)
class V2PreviewFrame:
    frame_id: str
    description: str
    entries: tuple[V2PreviewEntry, ...]


def _parse_header(header: str) -> tuple[str, str, str]:
    raw = " ".join(str(header or "").strip().split())
    if not raw:
        raise ScriptAuthoringError("Tag vazia.")
    parts = raw.split(maxsplit=1)
    kind = parts[0].upper()
    kind = kind.replace("Ç", "C").replace("Ã", "A").replace("É", "E")
    actor = parts[1].strip() if len(parts) > 1 else ""
    if kind == "DESCRICAO":
        if actor:
            raise ScriptAuthoringError("[DESCRIÇÃO] não recebe personagem.")
        return "DESCRICAO", "", ""
    if kind not in {"FALA", "PENSAMENTO"}:
        raise ScriptAuthoringError(
            f"Tag não reconhecida no modo V2: [{raw}]. Use [DESCRIÇÃO], [FALA ator], "
            "[FALA EXATA ator], [FALA INTERPRETADA ator] ou [PENSAMENTO ator]."
        )
    delivery = "adaptavel"
    if kind == "FALA":
        actor_parts = actor.split(maxsplit=1)
        mode = actor_parts[0].upper()
        mode = mode.replace("Ç", "C").replace("Ã", "A").replace("É", "E")
        if mode in {"EXATA", "INTERPRETADA", "INTERPRETATIVA"}:
            delivery = "exata" if mode == "EXATA" else "interpretada"
            actor = actor_parts[1].strip() if len(actor_parts) > 1 else ""
    if not actor:
        raise ScriptAuthoringError(f"[{kind}] exige um ator, por exemplo [{kind} camilly].")
    clean_actor = slugify(actor, fallback="")
    if not clean_actor:
        raise ScriptAuthoringError(f"Ator inválido em [{raw}].")
    return kind, clean_actor, delivery


def parse_v2_draft(draft: str) -> list[V2Instruction]:
    source = str(draft or "").strip()
    if not source:
        raise ScriptAuthoringError("Digite ao menos uma instrução.")
    matches = list(_TAG_PATTERN.finditer(source))
    if not matches:
        raise ScriptAuthoringError("Nenhuma tag V2 foi encontrada.")
    if source[: matches[0].start()].strip():
        raise ScriptAuthoringError("Existe texto antes da primeira tag.")

    items: list[V2Instruction] = []
    for match in matches:
        raw_header = " ".join(match.group(1).strip().split())
        kind, actor, delivery = _parse_header(raw_header)
        text = str(match.group(2) or "").strip()
        if not text:
            raise ScriptAuthoringError(f"[{raw_header}] precisa de conteúdo.")
        if kind == "DESCRICAO":
            canonical_header = "[DESCRIÇÃO]"
        elif kind == "FALA" and delivery != "adaptavel":
            mode = "EXATA" if delivery == "exata" else "INTERPRETADA"
            canonical_header = f"[FALA {mode} {actor}]"
        else:
            canonical_header = f"[{kind} {actor}]"
        items.append(
            V2Instruction(
                kind=kind,
                actor=actor,
                text=text,
                instruction=f"{canonical_header} {text}",
                delivery=delivery,
            )
        )
    return items


def validate_v2_sequence(items: Iterable[V2Instruction]) -> list[str]:
    materialized = list(items)
    errors: list[str] = []
    frame_open = False
    frame_count = 0
    for index, item in enumerate(materialized, start=1):
        if item.kind == "DESCRICAO":
            frame_open = True
            frame_count += 1
            continue
        if not frame_open:
            errors.append(
                f"Linha autoral {index}: [{item.kind} {item.actor}] precisa de [DESCRIÇÃO] anterior."
            )
    if frame_count == 0:
        errors.append("O roteiro V2 precisa ter ao menos uma [DESCRIÇÃO].")
    return errors


def compile_v2_rows(
    draft: str,
    *,
    package_id: str,
    script_version: str,
    frame_prefix: str,
    start_order: int = 10,
    order_step: int = 10,
    start_frame_number: int = 1,
) -> list[dict[str, object]]:
    clean_package = str(package_id or "").strip()
    clean_version = str(script_version or "").strip()
    if not clean_package.startswith("roleplay2026.") or clean_package.endswith("."):
        raise ScriptAuthoringError(
            "package_id deve seguir o formato roleplay2026.nome_da_historia."
        )
    if not clean_version:
        raise ScriptAuthoringError("Informe a script_version.")
    if int(start_order) < 0 or int(order_step) <= 0:
        raise ScriptAuthoringError("A order inicial deve ser positiva e o intervalo maior que zero.")
    if int(start_frame_number) <= 0:
        raise ScriptAuthoringError("O primeiro número de quadro deve ser maior que zero.")

    prefix = slugify(frame_prefix, fallback="quadro")
    items = parse_v2_draft(draft)
    errors = validate_v2_sequence(items)
    if errors:
        raise ScriptAuthoringError("\n".join(errors))

    rows: list[dict[str, object]] = []
    used_line_ids: set[str] = set()
    frame_number = int(start_frame_number) - 1
    current_frame = ""
    occurrence: dict[tuple[str, str], int] = defaultdict(int)

    for index, item in enumerate(items):
        if item.kind == "DESCRICAO":
            frame_number += 1
            current_frame = f"{prefix}_{frame_number:03d}"
            occurrence = defaultdict(int)
            line_id = f"{current_frame}_descricao"
        else:
            key = (item.actor, item.kind)
            occurrence[key] += 1
            suffix = "fala" if item.kind == "FALA" else "pensamento"
            line_id = f"{current_frame}_{item.actor}_{suffix}_{occurrence[key]:02d}"

        if line_id in used_line_ids:
            raise ScriptAuthoringError(f"line_id duplicado: {line_id}.")
        used_line_ids.add(line_id)
        rows.append(
            {
                "package_id": clean_package,
                "script_version": clean_version,
                "line_id": line_id,
                "order": int(start_order) + index * int(order_step),
                "instruction": item.instruction,
                "status": "active",
                "updated_at": "",
            }
        )
    return rows


def preview_v2_frames(
    draft: str,
    *,
    frame_prefix: str,
    start_frame_number: int = 1,
) -> list[V2PreviewFrame]:
    items = parse_v2_draft(draft)
    errors = validate_v2_sequence(items)
    if errors:
        raise ScriptAuthoringError("\n".join(errors))

    prefix = slugify(frame_prefix, fallback="quadro")
    frame_number = int(start_frame_number) - 1
    frames: list[V2PreviewFrame] = []
    current_id = ""
    description = ""
    entries: list[V2PreviewEntry] = []

    def flush() -> None:
        nonlocal entries
        if current_id:
            frames.append(
                V2PreviewFrame(
                    frame_id=current_id,
                    description=description,
                    entries=tuple(entries),
                )
            )
        entries = []

    for item in items:
        if item.kind == "DESCRICAO":
            flush()
            frame_number += 1
            current_id = f"{prefix}_{frame_number:03d}"
            description = item.text
        else:
            entries.append(V2PreviewEntry(item.kind, item.actor, item.text, item.delivery))
    flush()
    return frames


__all__ = [
    "ROTEIROS_COLUMNS",
    "V2Instruction",
    "V2PreviewEntry",
    "V2PreviewFrame",
    "compile_v2_rows",
    "parse_v2_draft",
    "preview_v2_frames",
    "rows_to_csv",
    "rows_to_tsv",
    "validate_v2_sequence",
]
