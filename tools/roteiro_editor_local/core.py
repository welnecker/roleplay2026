from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Iterable, Mapping
from xml.sax.saxutils import escape

OFFICIAL_COLUMNS = (
    "package_id",
    "script_version",
    "line_id",
    "order",
    "instruction",
    "status",
    "image_id",
)


def clean_image_prefix(value: object, fallback: str = "imagem") -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[^a-z0-9_-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_-")
    return text or fallback


def default_image_prefix(package_id: object) -> str:
    raw = str(package_id or "").strip().split(".")[-1]
    return clean_image_prefix(raw, fallback="imagem")


def allocate_image_ids(
    rows: Iterable[Mapping[str, object]],
    assigned_line_ids: Iterable[str],
    *,
    prefix: str,
    start_number: int = 1,
) -> dict[str, str]:
    assigned = {str(item or "").strip() for item in assigned_line_ids if str(item or "").strip()}
    current = max(1, int(start_number))
    clean_prefix = clean_image_prefix(prefix)
    result: dict[str, str] = {}
    for row in rows:
        line_id = str(row.get("line_id", "") or "").strip()
        if not line_id or line_id not in assigned:
            continue
        result[line_id] = f"{clean_prefix}{current}.webp"
        current += 1
    return result


def build_export_rows(
    rows: Iterable[Mapping[str, object]],
    image_ids: Mapping[str, str] | None = None,
) -> list[dict[str, object]]:
    images = dict(image_ids or {})
    result: list[dict[str, object]] = []
    for source in rows:
        line_id = str(source.get("line_id", "") or "").strip()
        row = {
            "package_id": str(source.get("package_id", "") or "").strip(),
            "script_version": str(source.get("script_version", "") or "").strip(),
            "line_id": line_id,
            "order": int(source.get("order", 0) or 0),
            "instruction": str(source.get("instruction", "") or "").strip(),
            "status": str(source.get("status", "active") or "active").strip() or "active",
            "image_id": str(images.get(line_id, source.get("image_id", "")) or "").strip(),
        }
        result.append(row)
    return result


def rows_to_csv_text(rows: Iterable[Mapping[str, object]]) -> str:
    materialized = build_export_rows(rows)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(OFFICIAL_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(materialized)
    return output.getvalue()


def rows_to_tsv_text(rows: Iterable[Mapping[str, object]]) -> str:
    materialized = build_export_rows(rows)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=list(OFFICIAL_COLUMNS),
        extrasaction="ignore",
        delimiter="\t",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(materialized)
    return output.getvalue()


def _column_letter(index: int) -> str:
    result = ""
    value = int(index)
    while value:
        value, remainder = divmod(value - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _inline_cell(ref: str, value: object, style: int) -> str:
    text = escape(str(value or ""))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def rows_to_xlsx_bytes(rows: Iterable[Mapping[str, object]]) -> bytes:
    materialized = build_export_rows(rows)
    matrix: list[list[object]] = [list(OFFICIAL_COLUMNS)]
    for row in materialized:
        matrix.append([row[column] for column in OFFICIAL_COLUMNS])

    xml_rows: list[str] = []
    for row_index, values in enumerate(matrix, start=1):
        cells: list[str] = []
        for col_index, value in enumerate(values, start=1):
            ref = f"{_column_letter(col_index)}{row_index}"
            if row_index > 1 and col_index == 4:
                cells.append(f'<c r="{ref}" s="3"><v>{int(value or 0)}</v></c>')
            else:
                cells.append(_inline_cell(ref, value, 1 if row_index == 1 else 2))
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    last_row = max(1, len(matrix))
    sheet_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <dimension ref="A1:G{last_row}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <cols>
    <col min="1" max="1" width="24" customWidth="1"/>
    <col min="2" max="2" width="16" customWidth="1"/>
    <col min="3" max="3" width="42" customWidth="1"/>
    <col min="4" max="4" width="10" customWidth="1"/>
    <col min="5" max="5" width="95" customWidth="1"/>
    <col min="6" max="6" width="14" customWidth="1"/>
    <col min="7" max="7" width="30" customWidth="1"/>
  </cols>
  <sheetData>{''.join(xml_rows)}</sheetData>
  <autoFilter ref="A1:G{last_row}"/>
</worksheet>'''

    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
    root_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="ROTEIROS" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FFD24369"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="4">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment horizontal="center" vertical="top"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return output.getvalue()


def convert_image_to_webp(
    source_bytes: bytes,
    *,
    quality: int = 88,
    max_dimension: int = 1600,
) -> bytes:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError(
            "Pillow não está instalado. Execute o lançador do editor para instalar as dependências locais."
        ) from exc

    with Image.open(io.BytesIO(source_bytes)) as source:
        image = ImageOps.exif_transpose(source)
        limit = max(320, int(max_dimension))
        if image.width > limit or image.height > limit:
            image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        output = io.BytesIO()
        image.save(
            output,
            format="WEBP",
            quality=max(50, min(100, int(quality))),
            method=6,
        )
        return output.getvalue()


def save_export_bundle(
    output_dir: str | Path,
    rows: Iterable[Mapping[str, object]],
    image_sources: Mapping[str, bytes],
    *,
    image_prefix: str,
    image_start_number: int = 1,
    quality: int = 88,
    max_dimension: int = 1600,
    project_meta: Mapping[str, object] | None = None,
    overwrite: bool = False,
) -> dict[str, object]:
    materialized = [dict(row) for row in rows]
    image_ids = allocate_image_ids(
        materialized,
        image_sources.keys(),
        prefix=image_prefix,
        start_number=image_start_number,
    )
    export_rows = build_export_rows(materialized, image_ids)

    root = Path(output_dir).expanduser().resolve()
    images_dir = root / "imagens"
    root.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    planned = [root / "roteiro.xlsx", root / "roteiro.csv", root / "roteiro.tsv", root / "projeto_roteiro.json"]
    planned.extend(images_dir / name for name in image_ids.values())
    conflicts = [path for path in planned if path.exists()]
    if conflicts and not overwrite:
        preview = ", ".join(path.name for path in conflicts[:5])
        raise FileExistsError(f"Já existem arquivos no destino ({preview}). Marque sobrescrever para substituí-los.")

    for line_id, image_id in image_ids.items():
        converted = convert_image_to_webp(
            image_sources[line_id],
            quality=quality,
            max_dimension=max_dimension,
        )
        (images_dir / image_id).write_bytes(converted)

    (root / "roteiro.xlsx").write_bytes(rows_to_xlsx_bytes(export_rows))
    (root / "roteiro.csv").write_text(rows_to_csv_text(export_rows), encoding="utf-8-sig", newline="")
    (root / "roteiro.tsv").write_text(rows_to_tsv_text(export_rows), encoding="utf-8", newline="")

    project = dict(project_meta or {})
    project.update(
        {
            "format_version": 1,
            "columns": list(OFFICIAL_COLUMNS),
            "image_ids": image_ids,
            "rows": export_rows,
        }
    )
    (root / "projeto_roteiro.json").write_text(
        json.dumps(project, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "root": root,
        "images_dir": images_dir,
        "image_ids": image_ids,
        "rows": export_rows,
        "xlsx": root / "roteiro.xlsx",
        "csv": root / "roteiro.csv",
        "tsv": root / "roteiro.tsv",
        "project": root / "projeto_roteiro.json",
    }


__all__ = [
    "OFFICIAL_COLUMNS",
    "allocate_image_ids",
    "build_export_rows",
    "clean_image_prefix",
    "convert_image_to_webp",
    "default_image_prefix",
    "rows_to_csv_text",
    "rows_to_tsv_text",
    "rows_to_xlsx_bytes",
    "save_export_bundle",
]
