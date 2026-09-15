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
    assert 'href="/termos-de-uso/"' in html
    assert 'href="/politica-de-privacidade/"' in html
    terms = (output_dir / "termos-de-uso" / "index.html").read_text(encoding="utf-8")
    privacy = (output_dir / "politica-de-privacidade" / "index.html").read_text(
        encoding="utf-8"
    )
    assert "Cada pagamento é unitário" in terms
    assert "uma execução" in terms
    assert "Não existe mensalidade, assinatura ou renovação automática" in terms
    assert "Mercado Pago" in privacy
    assert "SyncPay" not in terms + privacy
    assert "DramaLove" not in terms + privacy
    assert (output_dir / "_headers").is_file()
    assert (output_dir / "_redirects").is_file()
