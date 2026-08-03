from pathlib import Path


def test_interface_nao_depende_de_modulo_legado() -> None:
    source = Path("ui_components.py").read_text(encoding="utf-8")

    assert "ui_components_legacy" not in source
    assert not Path("ui_components_legacy.py").exists()


def test_interface_nao_conhece_historia_especifica() -> None:
    source = Path("ui_components.py").read_text(encoding="utf-8").casefold()

    assert "casada_frustrada" not in source
    assert "_pilot_package_id" not in source
    assert "2_piloto_supermercado.py" not in source
    assert "player_page_for(package)" in source


def test_tema_visual_esta_isolado_da_logica_de_card() -> None:
    components = Path("ui_components.py").read_text(encoding="utf-8")
    theme = Path("ui_theme.py").read_text(encoding="utf-8")

    assert "from ui_theme import CARD_CSS" in components
    assert "<style>" not in components
    assert "CARD_CSS" in theme
    assert "<style>" in theme
