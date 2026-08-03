from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PLAYER_PATH = ROOT / "pages" / "2_Historia_Editorial.py"
ENTRYPOINT_PATH = ROOT / "services" / "editorial_player.py"
RUNTIME_PATH = ROOT / "services" / "editorial_player_runtime.py"


def test_pagina_editorial_e_entrypoint_permanecem_minimos() -> None:
    page_source = PLAYER_PATH.read_text(encoding="utf-8")
    entrypoint_source = ENTRYPOINT_PATH.read_text(encoding="utf-8")

    assert "from services.editorial_player import run_editorial_player" in page_source
    assert "run_editorial_player()" in page_source
    assert "editorial_player_runtime" in entrypoint_source
    assert 'st.session_state.get("selected_package_id"' not in page_source


def test_player_editorial_resolve_pacote_selecionado_pelo_manifesto() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert 'st.session_state.get("selected_package_id"' in source
    assert "find_editorial_package(package_id)" in source
    assert "load_editorial_package(st.secrets, package)" in source


def test_player_editorial_nao_conhece_historia_ou_cenario_especificos() -> None:
    public_source = "\n".join(
        (
            PLAYER_PATH.read_text(encoding="utf-8"),
            ENTRYPOINT_PATH.read_text(encoding="utf-8"),
        )
    ).casefold()
    runtime_source = RUNTIME_PATH.read_text(encoding="utf-8").casefold()

    for forbidden in (
        "roleplay2026.casada_frustrada",
        'st.title("casada frustrada")',
        "bloco piloto: primeiro contato no supermercado",
    ):
        assert forbidden not in public_source
        assert forbidden not in runtime_source
    assert "package_title = package.manifest.card.title" in runtime_source


def test_sessoes_e_confirmacoes_sao_isoladas_por_package_id() -> None:
    source = RUNTIME_PATH.read_text(encoding="utf-8")

    assert 'END_CONFIRMATION_KEY = f"confirm_end:{PACKAGE_ID}"' in source
    assert 'prefix = f"editorial:{user_id}:{PACKAGE_ID}"' in source
    assert "package_id=PACKAGE_ID" in source


def test_player_legado_foi_removido() -> None:
    legacy = PLAYER_PATH.with_name("2_Piloto_Supermercado.py")

    assert not legacy.exists()
