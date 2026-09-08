from __future__ import annotations

from tools.roteiro_editor_local import core


def test_local_editor_exposes_current_sheet_contract() -> None:
    assert core.OFFICIAL_COLUMNS == (
        "package_id",
        "script_version",
        "line_id",
        "order",
        "instruction",
        "status",
        "image_id",
    )
