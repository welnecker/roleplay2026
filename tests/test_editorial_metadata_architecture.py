from __future__ import annotations

from pathlib import Path


MODULE = Path("services/editorial_metadata.py")


def test_contrato_de_metadados_nao_conhece_historia_especifica() -> None:
    source = MODULE.read_text(encoding="utf-8").casefold()

    for forbidden in (
        "casada_frustrada",
        "roleplay2026.",
        "mary",
        "supermercado",
        "motel",
    ):
        assert forbidden not in source


def test_contrato_usa_apenas_esquema_editorial() -> None:
    source = MODULE.read_text(encoding="utf-8")

    assert 'EDITORIAL_STATE_KEY = "editorial_state"' in source
    assert "LEGACY_STATE_KEY" not in source
    assert "include_legacy_aliases" not in source
    assert '"pilot_state"' not in source
    assert '"pilot_node"' not in source
