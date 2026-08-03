from __future__ import annotations

from pathlib import Path


PAGE = Path("pages/2_Historia_Editorial.py")
ENTRYPOINT = Path("services/editorial_player.py")
RUNTIME = Path("services/editorial_player_runtime.py")


def test_pagina_editorial_e_apenas_entrypoint_generico() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "run_editorial_player" in source
    assert "pilot_supermarket" not in source
    assert "pilot_diagnostics" not in source
    assert "supermarket_script_v2" not in source
    assert "casada_frustrada" not in source


def test_entrypoint_nao_conhece_historia_ou_cenario() -> None:
    source = ENTRYPOINT.read_text(encoding="utf-8").casefold()

    assert "editorial_player_runtime" in source
    assert "casada_frustrada" not in source
    assert "supermercado" not in source
    assert "mary" not in source
    assert "motel" not in source


def test_runtime_foi_isolado_para_migracao_gradual() -> None:
    assert RUNTIME.is_file()
    source = RUNTIME.read_text(encoding="utf-8")
    assert 'st.session_state.get("selected_package_id"' in source
    assert "load_editorial_package(st.secrets, package)" in source
