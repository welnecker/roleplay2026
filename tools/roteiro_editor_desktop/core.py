from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

COLUMNS = (
    "package_id",
    "script_version",
    "line_id",
    "order",
    "instruction",
    "status",
    "image_id",
)

_TAG_RE = re.compile(r"(?ms)^[ \t]*\[([^\]\n]+)\][ \t]*(.*?)(?=^[ \t]*\[[^\]\n]+\]|\Z)")


class EditorError(ValueError):
    pass


def slugify(value: str, fallback: str = "item") -> str:
    raw = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    raw = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
    return raw or fallback


@dataclass(frozen=True)
class Item:
    kind: str
    actor: str
    text: str
    instruction: str


def parse_draft(draft: str) -> list[Item]:
    source = str(draft or "").strip()
    if not source:
        raise EditorError("Digite ao menos uma instrução.")
    matches = list(_TAG_RE.finditer(source))
    if not matches:
        raise EditorError("Nenhuma tag V2 foi encontrada.")
    if source[: matches[0].start()].strip():
        raise EditorError("Existe texto antes da primeira tag.")

    items: list[Item] = []
    for match in matches:
        header = " ".join(match.group(1).strip().split())
        parts = header.split(maxsplit=1)
        kind_raw = unicodedata.normalize("NFKD", parts[0]).encode("ascii", "ignore").decode("ascii").upper()
        actor = parts[1].strip() if len(parts) > 1 else ""
        text = str(match.group(2) or "").strip()
        if not text:
            raise EditorError(f"[{header}] precisa de conteúdo.")

        if kind_raw == "DESCRICAO":
            if actor:
                raise EditorError("[DESCRIÇÃO] não recebe personagem.")
            items.append(Item("DESCRICAO", "", text, f"[DESCRIÇÃO] {text}"))
            continue

        if kind_raw not in {"FALA", "PENSAMENTO"}:
            raise EditorError(f"Tag não reconhecida: [{header}].")
        if not actor:
            raise EditorError(f"[{kind_raw}] exige um ator.")
        clean_actor = slugify(actor, fallback="")
        if not clean_actor:
            raise EditorError(f"Ator inválido em [{header}].")
        items.append(Item(kind_raw, clean_actor, text, f"[{kind_raw} {clean_actor}] {text}"))

    if not any(item.kind == "DESCRICAO" for item in items):
        raise EditorError("O roteiro precisa ter ao menos uma [DESCRIÇÃO].")
    frame_open = False
    for index, item in enumerate(items, start=1):
        if item.kind == "DESCRICAO":
            frame_open = True
        elif not frame_open:
            raise EditorError(f"Linha autoral {index}: [{item.kind} {item.actor}] precisa de [DESCRIÇÃO] anterior.")
    return items


def compile_rows(
    draft: str,
    *,
    package_id: str,
    script_version: str,
    frame_prefix: str,
    start_order: int = 10,
    order_step: int = 10,
    start_frame_number: int = 1,
    image_map: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    clean_package = str(package_id or "").strip()
    if not clean_package.startswith("roleplay2026.") or clean_package.endswith("."):
        raise EditorError("package_id deve seguir o formato roleplay2026.nome_da_historia.")
    clean_version = str(script_version or "").strip()
    if not clean_version:
        raise EditorError("Informe a script_version.")
    if int(order_step) <= 0:
        raise EditorError("O intervalo de order deve ser maior que zero.")
    if int(start_frame_number) <= 0:
        raise EditorError("O primeiro número do quadro deve ser maior que zero.")

    items = parse_draft(draft)
    prefix = slugify(frame_prefix, fallback="quadro")
    frame_number = int(start_frame_number) - 1
    current_frame = ""
    occurrences: dict[tuple[str, str], int] = {}
    rows: list[dict[str, object]] = []
    assigned = image_map or {}

    for index, item in enumerate(items):
        if item.kind == "DESCRICAO":
            frame_number += 1
            current_frame = f"{prefix}_{frame_number:03d}"
            occurrences = {}
            line_id = f"{current_frame}_descricao"
        else:
            key = (item.actor, item.kind)
            occurrences[key] = occurrences.get(key, 0) + 1
            suffix = "fala" if item.kind == "FALA" else "pensamento"
            line_id = f"{current_frame}_{item.actor}_{suffix}_{occurrences[key]:02d}"

        rows.append(
            {
                "package_id": clean_package,
                "script_version": clean_version,
                "line_id": line_id,
                "order": int(start_order) + index * int(order_step),
                "instruction": item.instruction,
                "status": "active",
                "image_id": str(assigned.get(line_id, "") or ""),
            }
        )
    return rows


def rows_to_csv(rows: Iterable[dict[str, object]]) -> str:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
    return buffer.getvalue()


def rows_to_tsv(rows: Iterable[dict[str, object]]) -> str:
    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore", delimiter="\t")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
    return buffer.getvalue()


def rows_to_xlsx_bytes(rows: list[dict[str, object]]) -> bytes:
    try:
        from openpyxl import Workbook
    except Exception as exc:
        raise EditorError("Não foi possível carregar o módulo Excel interno.") from exc
    wb = Workbook()
    ws = wb.active
    ws.title = "ROTEIROS"
    ws.append(list(COLUMNS))
    for row in rows:
        ws.append([row.get(column, "") for column in COLUMNS])
    ws.freeze_panes = "A2"
    widths = {"A": 28, "B": 16, "C": 42, "D": 10, "E": 90, "F": 12, "G": 24}
    for column, width in widths.items():
        ws.column_dimensions[column].width = width
    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def normalize_image_name(prefix: str, number: int) -> str:
    return f"{slugify(prefix, fallback='imagem')}{int(number)}.webp"


def save_project(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise EditorError("Projeto inválido.")
    return data


def export_package(
    destination: Path,
    *,
    rows: list[dict[str, object]],
    image_sources: dict[str, str],
    quality: int = 88,
    max_side: int = 1800,
    project_payload: dict[str, object] | None = None,
) -> Path:
    try:
        from PIL import Image
    except Exception as exc:
        raise EditorError("Não foi possível carregar o módulo interno de imagens.") from exc

    destination.mkdir(parents=True, exist_ok=True)
    images_dir = destination / "imagens"
    images_dir.mkdir(exist_ok=True)

    (destination / "roteiro.csv").write_text(rows_to_csv(rows), encoding="utf-8-sig")
    (destination / "roteiro.tsv").write_text(rows_to_tsv(rows), encoding="utf-8-sig")
    (destination / "roteiro.xlsx").write_bytes(rows_to_xlsx_bytes(rows))

    for image_id, source in image_sources.items():
        source_path = Path(source)
        if not source_path.exists():
            raise EditorError(f"Imagem não encontrada: {source_path}")
        with Image.open(source_path) as image:
            image = image.convert("RGB")
            if max(image.size) > int(max_side):
                image.thumbnail((int(max_side), int(max_side)), Image.Resampling.LANCZOS)
            image.save(images_dir / image_id, "WEBP", quality=int(quality), method=6)

    if project_payload is not None:
        save_project(destination / "projeto_roteiro.json", project_payload)
    return destination


def create_zip_bytes(folder: Path) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(folder))
    return out.getvalue()
