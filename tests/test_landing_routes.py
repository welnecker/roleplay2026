from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from flet_api.landing_routes import (
    install,
    landing_page_html,
    privacy_policy_html,
    terms_of_use_html,
)


def test_landing_page_presents_participant_positioning() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Você faz parte dela" in response.text
    assert "Descubra seu papel" in response.text
    assert "Você também é personagem" in response.text
    assert 'href="/app/"' in response.text
    assert 'href="/baixar"' not in response.text
    assert "Use online pelo celular ou computador" in response.text
    assert "sem instalar nada" in response.text
    assert "Windows" not in response.text
    assert "Você decide o que acontece" not in response.text
    assert "Suas escolhas mudam" not in response.text
    assert "Pagamento único por execução, sem assinatura" in response.text
    assert 'href="/termos-de-uso/"' in response.text
    assert 'href="/politica-de-privacidade/"' in response.text


def test_landing_page_has_indexing_and_security_headers() -> None:
    app = install(FastAPI())
    response = TestClient(app).get("/")

    assert '<meta name="robots" content="index,follow">' in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_conhecer_serves_landing_without_redirect_or_download() -> None:
    app = install(FastAPI())
    client = TestClient(app)

    response = client.get("/conhecer", follow_redirects=False)

    assert response.status_code == 200
    assert response.history == []
    assert response.headers["content-type"].startswith("text/html")
    assert "content-disposition" not in response.headers
    assert "Você faz parte dela" in response.text
    assert 'href="/baixar"' not in response.text
    assert 'href="/baixar/android"' not in response.text


def test_landing_media_routes_serve_packaged_assets() -> None:
    app = install(FastAPI())
    client = TestClient(app)

    reel = client.get("/midia/entrecenas-reel.mp4")
    poster = client.get("/midia/entrecenas-reel-poster.webp")
    icon = client.get("/midia/entrecenas-icone.svg")
    organized_reel = client.get("/midia/landing/entrecenas-reel.mp4")
    organized_icon = client.get("/midia/brand/entrecenas-icone.svg")

    assert reel.status_code == 200
    assert reel.headers["content-type"].startswith("video/mp4")
    assert len(reel.content) > 400_000
    assert poster.status_code == 200
    assert poster.headers["content-type"].startswith("image/webp")
    assert icon.status_code == 200
    assert icon.headers["content-type"].startswith("image/svg+xml")
    assert organized_reel.status_code == 200
    assert organized_icon.status_code == 200


def test_landing_routes_install_is_idempotent() -> None:
    app = FastAPI()
    install(app)
    install(app)

    paths = [route.path for route in app.routes]
    assert paths.count("/") == 1
    assert paths.count("/conhecer") == 1
    assert paths.count("/termos-de-uso") == 1
    assert paths.count("/termos-de-uso/") == 1
    assert paths.count("/politica-de-privacidade") == 1
    assert paths.count("/politica-de-privacidade/") == 1
    assert paths.count("/midia/entrecenas-reel.mp4") == 1
    assert paths.count("/midia/entrecenas-reel-poster.webp") == 1
    assert paths.count("/midia/entrecenas-icone.svg") == 1


def test_landing_page_accepts_cloudflare_destinations() -> None:
    html = landing_page_html(
        app_url="https://app.entrecenas-roleplay.com.br",
        media_base_url="https://midia.entrecenas-roleplay.com.br",
        site_url="https://entrecenas-roleplay.com.br",
    )

    assert 'href="https://app.entrecenas-roleplay.com.br/"' in html
    assert "https://midia.entrecenas-roleplay.com.br/landing/entrecenas-reel.mp4" in html
    assert "https://midia.entrecenas-roleplay.com.br/brand/entrecenas-icone.svg" in html


def test_legal_pages_match_real_unit_payment_model() -> None:
    app = install(FastAPI())
    client = TestClient(app)

    terms = client.get("/termos-de-uso/")
    privacy = client.get("/politica-de-privacidade/")

    assert terms.status_code == 200
    assert privacy.status_code == 200
    assert "Cada pagamento é unitário" in terms.text
    assert "uma execução do card e do roteiro" in terms.text
    assert "novas execuções exigem pagamentos separados" in terms.text
    assert "Não existe mensalidade, assinatura ou renovação automática" in terms.text
    assert "Mercado Pago" in terms.text
    assert "Mercado Pago" in privacy.text
    assert "Render" in privacy.text
    assert "Cloudflare/R2" in privacy.text
    assert "DramaLove" not in terms.text + privacy.text
    assert "SyncPay" not in terms.text + privacy.text


def test_legal_page_helpers_replace_contact_and_canonical_url() -> None:
    privacy = privacy_policy_html(
        site_url="https://entrecenas-roleplay.com.br",
        media_base_url="https://midia.entrecenas-roleplay.com.br",
        contact_email="privacidade@example.com",
    )
    terms = terms_of_use_html(contact_email="suporte@example.com")

    assert 'href="https://entrecenas-roleplay.com.br/politica-de-privacidade/"' in privacy
    assert "mailto:privacidade@example.com" in privacy
    assert "mailto:suporte@example.com" in terms
