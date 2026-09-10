from __future__ import annotations

from pathlib import Path

from scripts.build_cloudflare_landing import build


def test_cloudflare_landing_build_uses_external_app_and_r2_urls() -> None:
    output_dir = build()
    html = (output_dir / "index.html").read_text(encoding="utf-8")

    assert output_dir == Path("cloudflare/landing/dist").resolve()
    assert 'href="https://app.entrecenas-roleplay.com.br/app/"' in html
    assert "https://midia.entrecenas-roleplay.com.br/landing/entrecenas-reel.mp4" in html
    assert "Instalar no Android" not in html
    assert (output_dir / "_headers").is_file()
    assert (output_dir / "_redirects").is_file()
