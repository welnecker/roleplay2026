from pathlib import Path


def test_library_theme_uses_requested_green_and_beige_bands() -> None:
    source = Path("ui_theme.py").read_text(encoding="utf-8")

    assert "--rp-brand-green:#0c2e2d" in source
    assert "--rp-library-body:#d7d0bb" in source
    assert '[data-testid="stAppViewContainer"]:has(.story-flip-shell)' in source
    assert "calc(100% - 5rem)" in source


def test_login_green_remains_scoped_and_available() -> None:
    source = Path("ui_theme.py").read_text(encoding="utf-8")

    assert "--rp-login-green:var(--rp-brand-green)" in source
    assert 'input[aria-label="E-mail"]' in source
