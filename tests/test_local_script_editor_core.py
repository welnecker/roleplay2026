from __future__ import annotations

import io
import zipfile

from tools.roteiro_editor_local.core import (
    OFFICIAL_COLUMNS,
    allocate_image_ids,
    build_export_rows,
    rows_to_tsv_text,
    rows_to_xlsx_bytes,
)


def _rows() -> list[dict[str, object]]:
    return [
        {
            "package_id": "roleplay2026.camilly",
            "script_version": "200",
            "line_id": "encontro_001_descricao",
            "order": 10,
            "instruction": "[DESCRIÇÃO] Camilly se aproxima do carro.",
            "status": "active",
            "updated_at": "ignorar",
        },
        {
            "package_id": "roleplay2026.camilly",
            "script_version": "200",
            "line_id": "encontro_001_camilly_fala_01",
            "order": 20,
            "instruction": "[FALA camilly] Oi, {{nome}}...",
            "status": "active",
            "updated_at": "ignorar",
        },
        {
            "package_id": "roleplay2026.camilly",
            "script_version": "200",
            "line_id": "encontro_002_descricao",
            "order": 30,
            "instruction": "[DESCRIÇÃO] Camilly entra no carro.",
            "status": "active",
            "updated_at": "ignorar",
        },
    ]


def test_allocate_image_ids_follows_script_order() -> None:
    image_ids = allocate_image_ids(
        _rows(),
        {"encontro_002_descricao", "encontro_001_descricao"},
        prefix="camilly",
        start_number=7,
    )

    assert image_ids == {
        "encontro_001_descricao": "camilly7.webp",
        "encontro_002_descricao": "camilly8.webp",
    }


def test_export_rows_have_exact_current_header_without_updated_at() -> None:
    export_rows = build_export_rows(
        _rows(),
        {"encontro_001_descricao": "camilly1.webp"},
    )

    assert tuple(export_rows[0].keys()) == OFFICIAL_COLUMNS
    assert "updated_at" not in export_rows[0]
    assert export_rows[0]["image_id"] == "camilly1.webp"
    assert export_rows[1]["image_id"] == ""


def test_tsv_header_matches_google_sheet_contract() -> None:
    tsv = rows_to_tsv_text(build_export_rows(_rows()))
    assert tsv.splitlines()[0] == "\t".join(OFFICIAL_COLUMNS)


def test_xlsx_contains_roteiros_sheet_and_seven_columns() -> None:
    workbook = rows_to_xlsx_bytes(build_export_rows(_rows()))
    assert workbook.startswith(b"PK")

    with zipfile.ZipFile(io.BytesIO(workbook)) as archive:
        workbook_xml = archive.read("xl/workbook.xml").decode("utf-8")
        sheet_xml = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")

    assert 'name="ROTEIROS"' in workbook_xml
    assert 'dimension ref="A1:G4"' in sheet_xml
    for header in OFFICIAL_COLUMNS:
        assert f">{header}<" in sheet_xml
