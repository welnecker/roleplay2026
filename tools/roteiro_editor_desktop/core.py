from __future__ import annotations

import csv
import json
import re
import unicodedata
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from zipfile import ZIP_DEFLATED, ZipFile

from roleplay_shared.onomatopoeia import OnomatopoeiaEffect, parse_onomatopoeia_header

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
_CAST_NAME_RE = re.compile(r"\{\{nome:([a-zA-Z0-9_-]+)\}\}")
CAST_GENDERS = ("feminine", "masculine", "neutral")


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
    delivery: str = "adaptavel"
    effect: OnomatopoeiaEffect | None = None


def normalize_cast_members(value: object) -> list[dict[str, str]]:
    """Normaliza o elenco genérico salvo pelo editor e aceito pelo manifesto."""

    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditorError("O elenco deve ser uma lista de personagens.")
    result: list[dict[str, str]] = []
    for index, raw in enumerate(value, start=1):
        if not isinstance(raw, Mapping):
            raise EditorError(f"Personagem {index}: configuração inválida.")
        actor_id = slugify(str(raw.get("actor_id", "") or ""), fallback="")
        label = str(raw.get("label", "") or "").strip()
        default_name = str(raw.get("default_name", "") or "").strip()
        gender = str(raw.get("gender", "neutral") or "neutral").strip().casefold()
        gender = {
            "feminino": "feminine",
            "masculino": "masculine",
            "neutro": "neutral",
        }.get(gender, gender)
        if not actor_id:
            raise EditorError(f"Personagem {index}: informe um ID estrutural.")
        if not label:
            raise EditorError(f"Personagem {index}: informe o papel na trama.")
        if not default_name:
            raise EditorError(f"Personagem {index}: informe o nome inicial.")
        if len(default_name) > 40:
            raise EditorError(f"Personagem {index}: o nome inicial aceita até 40 caracteres.")
        if any(character in default_name for character in "\r\n\t<>"):
            raise EditorError(f"Personagem {index}: o nome inicial contém caracteres inválidos.")
        if gender not in CAST_GENDERS:
            raise EditorError(f"Personagem {index}: gênero estrutural inválido.")
        result.append(
            {
                "actor_id": actor_id,
                "label": label,
                "default_name": default_name,
                "gender": gender,
            }
        )
    if not result:
        raise EditorError("Cadastre ao menos um personagem no elenco.")
    actor_ids = [member["actor_id"] for member in result]
    if len(actor_ids) != len(set(actor_ids)):
        raise EditorError("Cada personagem precisa ter um ID estrutural diferente.")
    names = [member["default_name"].casefold() for member in result]
    if len(names) != len(set(names)):
        raise EditorError("Cada personagem precisa ter um nome inicial diferente.")
    return result


def cast_members_from_legacy_actors(value: object) -> list[dict[str, str]]:
    """Abre projetos antigos, convertendo a lista por vírgulas em elenco editável."""

    actors: list[str] = []
    for raw in str(value or "").replace(";", ",").split(","):
        actor_id = slugify(raw.strip(), fallback="")
        if actor_id and actor_id not in actors:
            actors.append(actor_id)
    if not actors:
        actors = ["usuario"]
    return [
        {
            "actor_id": actor_id,
            "label": "O participante" if actor_id == "usuario" else "A personagem",
            "default_name": "Usuário" if actor_id == "usuario" else actor_id.replace("_", " ").title(),
            "gender": "neutral",
        }
        for actor_id in actors
    ]


def validate_draft_cast(draft: str, cast_members: object) -> list[dict[str, str]]:
    """Garante que tags narrativas e marcadores de nome usem atores declarados."""

    members = normalize_cast_members(cast_members)
    allowed = {member["actor_id"] for member in members}
    for item in parse_draft(draft):
        actor = item.actor.removesuffix("_balao")
        if actor and actor not in allowed:
            raise EditorError(
                f"O ator '{actor}' aparece no roteiro, mas não está cadastrado no elenco."
            )
    for match in _CAST_NAME_RE.finditer(str(draft or "")):
        actor = slugify(match.group(1), fallback="")
        if actor not in allowed:
            raise EditorError(
                f"O marcador '{{{{nome:{actor}}}}}' usa um personagem não cadastrado."
            )
    return members


def cast_manifest_yaml(cast_members: object) -> str:
    members = normalize_cast_members(cast_members)
    lines = ["cast_customization:", "  enabled: true", "  members:"]
    for member in members:
        lines.extend(
            (
                f"    - actor_id: {member['actor_id']}",
                f"      label: {json.dumps(member['label'], ensure_ascii=False)}",
                f"      default_name: {json.dumps(member['default_name'], ensure_ascii=False)}",
                f"      gender: {member['gender']}",
            )
        )
    return "\n".join(lines) + "\n"


def cast_tag_guide(cast_members: object) -> str:
    members = normalize_cast_members(cast_members)
    lines = [
        "ELENCO E TAGS DO ROTEIRO",
        "",
        "Os IDs são estruturais e não mudam quando o usuário troca os nomes.",
        "Use {{nome:actor_id}} sempre que um nome visível aparecer no texto.",
        "",
    ]
    for member in members:
        actor_id = member["actor_id"]
        lines.extend(
            (
                f"{member['label']} — nome inicial: {member['default_name']}",
                f"  Nome no texto: {{{{nome:{actor_id}}}}}",
                f"  Fala: [FALA {actor_id}]",
                f"  Pensamento: [PENSAMENTO {actor_id}]",
                "",
            )
        )
    return "\n".join(lines)


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

        if kind_raw == "FIM_HISTORIA":
            if actor:
                raise EditorError("[FIM_HISTORIA] não recebe argumentos dentro da tag.")
            instruction = "[FIM_HISTORIA]" + (f" {text}" if text else "")
            items.append(Item("FIM_HISTORIA", "", text, instruction, ""))
            continue

        if kind_raw == "ONOMATOPEIA":
            if text:
                raise EditorError("[ONOMATOPEIA] não recebe texto fora da tag.")
            try:
                effect = parse_onomatopoeia_header(header)
            except ValueError as exc:
                raise EditorError(str(exc)) from exc
            items.append(
                Item(
                    "ONOMATOPEIA",
                    "",
                    "",
                    f"[{effect.canonical_header()}]",
                    "",
                    effect,
                )
            )
            continue

        if not text:
            raise EditorError(f"[{header}] precisa de conteúdo.")

        if kind_raw == "DESCRICAO":
            if actor:
                raise EditorError("[DESCRIÇÃO] não recebe personagem.")
            items.append(Item("DESCRICAO", "", text, f"[DESCRIÇÃO] {text}", ""))
            continue

        if kind_raw not in {"FALA", "PENSAMENTO"}:
            raise EditorError(f"Tag não reconhecida: [{header}].")
        delivery = "adaptavel"
        if kind_raw == "FALA":
            actor_parts = actor.split(maxsplit=1)
            mode = slugify(actor_parts[0], "").upper() if actor_parts else ""
            if mode in {"EXATA", "INTERPRETADA", "INTERPRETATIVA"}:
                delivery = "exata" if mode == "EXATA" else "interpretada"
                actor = actor_parts[1].strip() if len(actor_parts) > 1 else ""
        if not actor:
            raise EditorError(f"[{kind_raw}] exige um ator.")
        clean_actor = slugify(actor, fallback="")
        if not clean_actor:
            raise EditorError(f"Ator inválido em [{header}].")
        if kind_raw == "FALA" and delivery != "adaptavel":
            mode = "EXATA" if delivery == "exata" else "INTERPRETADA"
            instruction = f"[FALA {mode} {clean_actor}] {text}"
        else:
            instruction = f"[{kind_raw} {clean_actor}] {text}"
        items.append(Item(kind_raw, clean_actor, text, instruction, delivery))

    if not any(item.kind == "DESCRICAO" for item in items):
        raise EditorError("O roteiro precisa ter ao menos uma [DESCRIÇÃO].")
    endings = [index for index, item in enumerate(items) if item.kind == "FIM_HISTORIA"]
    if len(endings) > 1:
        raise EditorError("O roteiro deve possuir no máximo uma tag [FIM_HISTORIA].")
    if endings and endings[0] != len(items) - 1:
        raise EditorError("[FIM_HISTORIA] deve ser a última linha do roteiro.")
    frame_open = False
    for index, item in enumerate(items, start=1):
        if item.kind == "DESCRICAO":
            frame_open = True
        elif not frame_open:
            tag = item.kind if not item.actor else f"{item.kind} {item.actor}"
            raise EditorError(
                f"Linha autoral {index}: [{tag}] precisa de [DESCRIÇÃO] anterior."
            )
    for index, item in enumerate(items):
        if item.kind != "ONOMATOPEIA":
            continue
        if index + 1 >= len(items) or items[index + 1].kind not in {"FALA", "PENSAMENTO"}:
            raise EditorError(
                "[ONOMATOPEIA] precisa ficar imediatamente antes da FALA ou PENSAMENTO correspondente."
            )
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
        elif item.kind == "FIM_HISTORIA":
            line_id = f"{current_frame}_fim_historia"
        elif item.kind == "ONOMATOPEIA":
            key = ("", item.kind)
            occurrences[key] = occurrences.get(key, 0) + 1
            line_id = f"{current_frame}_onomatopeia_{occurrences[key]:02d}"
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
        cast_members = project_payload.get("cast_members")
        if cast_members:
            (destination / "elenco_manifest.yaml").write_text(
                cast_manifest_yaml(cast_members),
                encoding="utf-8",
            )
            (destination / "ELENCO-E-TAGS.txt").write_text(
                cast_tag_guide(cast_members),
                encoding="utf-8",
            )
    return destination


def create_zip_bytes(folder: Path) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(folder))
    return out.getvalue()
