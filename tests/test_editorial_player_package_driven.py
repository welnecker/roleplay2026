from __future__ import annotations

from pathlib import Path


PLAYER_PATH = (
    Path(__file__).resolve().parent.parent
    / "pages"
    / "2_Historia_Editorial.py"
)
LEGACY_PLAYER_PATH = (
    Path(__file__).resolve().parent.parent
    / "pages"
    / "2_Piloto_Supermercado.py"
)


def test_player_editorial_resolve_pacote_selecionado_pelo_manifesto() -> None:
    source = PLAYER_PATH.read_text(encoding="utf-8")

    assert 'st.session_state.get("selected_package_id"' in source
    assert "find_editorial_package(package_id)" in source
    assert "load_editorial_package(st.secrets, package)" in source


def test_player_editorial_nao_conhece_historia_ou_cenario_especificos() -> None:
    source = PLAYER_PATH.read_text(encoding="utf-8").casefold()

    assert "roleplay2026.casada_frustrada" not in source
    assert 'st.title("casada frustrada")' not in source
    assert "bloco piloto: primeiro contato no supermercado" not in source
    assert "package_title = package.manifest.card.title" in source


def test_sessoes_e_confirmacoes_sao_isoladas_por_package_id() -> None:
    source = PLAYER_PATH.read_text(encoding="utf-8")

    assert 'END_CONFIRMATION_KEY = f"confirm_end:{PACKAGE_ID}"' in source
    assert 'prefix = f"editorial:{user_id}:{PACKAGE_ID}"' in source
    assert "package_id=PACKAGE_ID" in source


def test_arquivo_antigo_e_apenas_fachada_de_compatibilidade() -> None:
    source = LEGACY_PLAYER_PATH.read_text(encoding="utf-8")

    assert 'with_name("2_Historia_Editorial.py")' in source
    assert "selected_package_id" not in source
    assert "load_editorial_package" not in source
