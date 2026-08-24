from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "roteiro_editor_desktop" / "core.py"
spec = importlib.util.spec_from_file_location("roteiro_editor_desktop_core", MODULE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def _draft() -> str:
    return """[DESCRIÇÃO] Camilly entra no carro.
[FALA camilly] Oi, {{nome}}.
[PENSAMENTO camilly] Eu observo a reação dele.
[DESCRIÇÃO] Camilly fecha a porta.
[FALA usuario] Tudo bem?
"""


def test_columns_match_current_sheet_contract() -> None:
    assert core.COLUMNS == (
        "package_id",
        "script_version",
        "line_id",
        "order",
        "instruction",
        "status",
        "image_id",
    )


def test_compile_rows_generates_v2_ids_and_orders() -> None:
    rows = core.compile_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
        start_order=10,
        order_step=10,
        start_frame_number=1,
    )
    assert [row["line_id"] for row in rows] == [
        "encontro_001_descricao",
        "encontro_001_camilly_fala_01",
        "encontro_001_camilly_pensamento_01",
        "encontro_002_descricao",
        "encontro_002_usuario_fala_01",
    ]
    assert [row["order"] for row in rows] == [10, 20, 30, 40, 50]
    assert all(tuple(row.keys()) == core.COLUMNS for row in rows)


def test_balloon_actor_suffix_is_preserved_in_export() -> None:
    rows = core.compile_rows(
        "[DESCRIÇÃO] Cena inicial.\n[FALA camilly_balao] Olha pra mim.",
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
    )
    assert rows[1]["instruction"] == "[FALA camilly_balao] Olha pra mim."
    assert rows[1]["line_id"] == "encontro_001_camilly_balao_fala_01"


def test_image_map_is_applied_only_to_exact_line() -> None:
    rows = core.compile_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
        image_map={"encontro_001_descricao": "camilly1.webp", "encontro_001_camilly_pensamento_01": "camilly2.webp"},
    )
    assert rows[0]["image_id"] == "camilly1.webp"
    assert rows[1]["image_id"] == ""
    assert rows[2]["image_id"] == "camilly2.webp"


def test_image_name_is_webp_and_sequential() -> None:
    assert core.normalize_image_name("Camilly", 1) == "camilly1.webp"
    assert core.normalize_image_name("Casada frustrada", 12) == "casada_frustrada12.webp"


def test_csv_header_has_no_updated_at() -> None:
    rows = core.compile_rows(
        "[DESCRIÇÃO] Cena inicial.",
        package_id="roleplay2026.teste",
        script_version="1",
        frame_prefix="cena",
    )
    header = core.rows_to_csv(rows).splitlines()[0]
    assert header == "package_id,script_version,line_id,order,instruction,status,image_id"
    assert "updated_at" not in header
