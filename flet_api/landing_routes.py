from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse, HTMLResponse


LANDING_MEDIA_DIR = Path(__file__).resolve().parent.parent / "static" / "landing"
REEL_PATH = LANDING_MEDIA_DIR / "entrecenas-reel.mp4"
REEL_POSTER_PATH = LANDING_MEDIA_DIR / "entrecenas-reel-poster.webp"
BRAND_ICON_PATH = Path(__file__).resolve().parent.parent / "static" / "entrecenas-icon.svg"


def landing_page_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0c2e2d">
  <meta name="description" content="EntreCenas: histórias interativas para adultos. Escolha um card, descubra seu papel e participe diretamente de cada cena.">
  <meta name="robots" content="index,follow">
  <meta property="og:type" content="website">
  <meta property="og:locale" content="pt_BR">
  <meta property="og:site_name" content="EntreCenas">
  <meta property="og:title" content="EntreCenas — Você faz parte da história">
  <meta property="og:description" content="Em cada card, uma história. Em cada história, um papel para você viver.">
  <meta property="og:url" content="https://entrecenas-roleplay.com.br/conhecer">
  <meta property="og:image" content="https://entrecenas-roleplay.com.br/midia/entrecenas-reel-poster.webp">
  <meta property="og:image:width" content="720">
  <meta property="og:image:height" content="1280">
  <link rel="canonical" href="https://entrecenas-roleplay.com.br/conhecer">
  <link rel="icon" href="/midia/entrecenas-icone.svg" type="image/svg+xml">
  <title>EntreCenas — Você faz parte da história</title>
  <style>
    :root {
      color-scheme: dark;
      --ink: #071918;
      --green: #0c2e2d;
      --green-soft: #153f3d;
      --green-line: #285654;
      --rose: #d24369;
      --rose-light: #f05b91;
      --cream: #fff8fb;
      --muted: #c7d7d5;
      --shadow: 0 28px 90px rgba(0, 0, 0, .34);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-width: 320px;
      background:
        radial-gradient(circle at 82% 8%, rgba(210, 67, 105, .18), transparent 28rem),
        radial-gradient(circle at 12% 48%, rgba(59, 133, 126, .16), transparent 34rem),
        var(--ink);
      color: var(--cream);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    a { color: inherit; }
    img, video { display: block; max-width: 100%; }
    .shell { width: min(1120px, calc(100% - 40px)); margin-inline: auto; }
    .skip {
      position: absolute;
      left: -9999px;
      top: 8px;
      z-index: 20;
      padding: 10px 14px;
      border-radius: 10px;
      background: var(--cream);
      color: var(--green);
    }
    .skip:focus { left: 12px; }

    header {
      position: relative;
      z-index: 3;
      border-bottom: 1px solid rgba(255, 255, 255, .08);
      background: rgba(7, 25, 24, .76);
      backdrop-filter: blur(16px);
    }
    .nav {
      min-height: 76px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
      font-size: 1.08rem;
      font-weight: 850;
      letter-spacing: -.02em;
    }
    .brand img { width: 42px; height: 42px; border-radius: 10px; }
    nav { display: flex; align-items: center; gap: 24px; }
    nav a { color: var(--muted); text-decoration: none; font-weight: 650; }
    nav a:hover, nav a:focus-visible { color: var(--cream); }

    .button {
      display: inline-flex;
      min-height: 52px;
      align-items: center;
      justify-content: center;
      border: 1px solid transparent;
      border-radius: 999px;
      padding: 14px 24px;
      background: linear-gradient(135deg, var(--rose-light), var(--rose));
      color: white;
      text-decoration: none;
      font-weight: 850;
      box-shadow: 0 16px 36px rgba(210, 67, 105, .24);
      transition: transform .2s ease, box-shadow .2s ease;
    }
    .button:hover, .button:focus-visible {
      transform: translateY(-2px);
      box-shadow: 0 20px 44px rgba(210, 67, 105, .34);
    }
    .button.secondary {
      border-color: var(--green-line);
      background: rgba(255, 255, 255, .035);
      box-shadow: none;
      color: var(--cream);
    }
    .button.small { min-height: 44px; padding: 10px 19px; }

    .hero {
      min-height: calc(100svh - 76px);
      display: grid;
      grid-template-columns: minmax(0, 1.08fr) minmax(300px, .72fr);
      align-items: center;
      gap: clamp(44px, 8vw, 104px);
      padding-block: clamp(52px, 8vw, 96px);
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 9px;
      margin: 0 0 18px;
      color: #ffabc5;
      font-size: .82rem;
      font-weight: 850;
      letter-spacing: .13em;
      text-transform: uppercase;
    }
    .eyebrow::before { content: ""; width: 28px; height: 2px; background: var(--rose-light); }
    h1, h2, h3, p { text-wrap: balance; }
    h1 {
      max-width: 760px;
      margin: 0;
      font-size: clamp(3rem, 7.4vw, 6.4rem);
      line-height: .94;
      letter-spacing: -.065em;
    }
    h1 span { color: var(--rose-light); }
    .lead {
      max-width: 680px;
      margin: 26px 0 0;
      color: var(--muted);
      font-size: clamp(1.05rem, 2vw, 1.3rem);
    }
    .actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 32px; }
    .facts { display: flex; flex-wrap: wrap; gap: 10px 18px; margin-top: 24px; color: #9fb8b5; font-size: .92rem; }
    .facts span { display: inline-flex; align-items: center; gap: 7px; }
    .facts span::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--rose-light); }

    .phone-wrap { position: relative; justify-self: center; }
    .phone-wrap::before {
      content: "";
      position: absolute;
      inset: 12% -18%;
      z-index: -1;
      border-radius: 50%;
      background: rgba(210, 67, 105, .24);
      filter: blur(70px);
    }
    .phone {
      position: relative;
      width: min(360px, 82vw);
      aspect-ratio: 9 / 16;
      overflow: hidden;
      border: 9px solid #173c3a;
      border-radius: 42px;
      background: #0a1e1d;
      box-shadow: var(--shadow);
    }
    .phone video { width: 100%; height: 100%; object-fit: cover; }
    .phone::after {
      content: "";
      position: absolute;
      inset: 0;
      border-radius: 32px;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.12);
      pointer-events: none;
    }
    .phone-label {
      position: absolute;
      right: -18px;
      bottom: 48px;
      padding: 12px 16px;
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 16px;
      background: rgba(12, 46, 45, .9);
      box-shadow: 0 14px 38px rgba(0,0,0,.28);
      font-size: .86rem;
      font-weight: 800;
      backdrop-filter: blur(12px);
    }

    section { padding-block: clamp(72px, 9vw, 118px); }
    .section-head { max-width: 760px; margin-bottom: 44px; }
    h2 { margin: 0; font-size: clamp(2.2rem, 5vw, 4.2rem); line-height: 1; letter-spacing: -.05em; }
    .section-head p { margin: 18px 0 0; color: var(--muted); font-size: 1.08rem; }
    .steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; counter-reset: steps; }
    .step {
      min-height: 260px;
      padding: 28px;
      border: 1px solid var(--green-line);
      border-radius: 26px;
      background: linear-gradient(145deg, rgba(255,255,255,.065), rgba(255,255,255,.022));
      counter-increment: steps;
    }
    .step::before {
      content: "0" counter(steps);
      display: block;
      margin-bottom: 52px;
      color: var(--rose-light);
      font-size: .85rem;
      font-weight: 900;
      letter-spacing: .12em;
    }
    .step h3 { margin: 0; font-size: 1.45rem; }
    .step p { margin: 12px 0 0; color: var(--muted); }

    .manifesto {
      position: relative;
      overflow: hidden;
      border-block: 1px solid var(--green-line);
      background: var(--green);
    }
    .manifesto-grid { display: grid; grid-template-columns: .75fr 1.25fr; align-items: center; gap: 64px; }
    .mark {
      width: min(260px, 58vw);
      aspect-ratio: 1;
      border-radius: 62px;
      box-shadow: var(--shadow);
    }
    blockquote { margin: 0; font-size: clamp(2.25rem, 5.5vw, 5rem); line-height: 1.03; letter-spacing: -.055em; font-weight: 850; }
    blockquote strong { color: var(--rose-light); }

    .experience-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
    .experience {
      display: flex;
      min-height: 350px;
      flex-direction: column;
      justify-content: space-between;
      padding: clamp(28px, 5vw, 46px);
      border: 1px solid var(--green-line);
      border-radius: 30px;
      background: rgba(255,255,255,.035);
    }
    .experience.featured {
      border-color: rgba(240,91,145,.55);
      background: linear-gradient(145deg, rgba(210,67,105,.2), rgba(255,255,255,.035));
    }
    .tag {
      align-self: flex-start;
      padding: 7px 11px;
      border: 1px solid rgba(255,255,255,.14);
      border-radius: 999px;
      color: #ffd9e5;
      font-size: .76rem;
      font-weight: 850;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    .experience h3 { margin: 24px 0 0; font-size: clamp(1.8rem, 3.5vw, 3rem); line-height: 1.02; letter-spacing: -.04em; }
    .experience p { color: var(--muted); }

    .faq { display: grid; grid-template-columns: .8fr 1.2fr; gap: 68px; align-items: start; }
    .questions { display: grid; gap: 12px; }
    details { border: 1px solid var(--green-line); border-radius: 18px; background: rgba(255,255,255,.03); padding: 20px 22px; }
    summary { cursor: pointer; font-weight: 800; }
    details p { margin: 13px 0 0; color: var(--muted); }

    .final-card {
      padding: clamp(40px, 8vw, 86px);
      border: 1px solid rgba(240,91,145,.45);
      border-radius: 36px;
      background:
        radial-gradient(circle at 88% 20%, rgba(240,91,145,.25), transparent 24rem),
        var(--green);
      text-align: center;
      box-shadow: var(--shadow);
    }
    .final-card h2 { max-width: 800px; margin-inline: auto; }
    .final-card p { max-width: 630px; margin: 20px auto 30px; color: var(--muted); font-size: 1.08rem; }

    footer { padding: 34px 0 48px; color: #89a3a0; font-size: .88rem; }
    .footer-row { display: flex; align-items: center; justify-content: space-between; gap: 20px; border-top: 1px solid rgba(255,255,255,.08); padding-top: 28px; }

    @media (max-width: 820px) {
      nav > a:not(.button) { display: none; }
      .hero { grid-template-columns: 1fr; text-align: center; }
      .hero-copy { display: flex; flex-direction: column; align-items: center; }
      .eyebrow::before { display: none; }
      .lead { max-width: 590px; }
      .actions, .facts { justify-content: center; }
      .phone-wrap { margin-top: 10px; }
      .steps, .experience-grid { grid-template-columns: 1fr; }
      .manifesto-grid, .faq { grid-template-columns: 1fr; }
      .mark { justify-self: center; }
      .step { min-height: 220px; }
      .step::before { margin-bottom: 34px; }
    }
    @media (max-width: 520px) {
      .shell { width: min(100% - 28px, 1120px); }
      .nav { min-height: 68px; }
      .brand img { width: 38px; height: 38px; }
      .nav .button { padding-inline: 16px; font-size: .9rem; }
      .hero { min-height: auto; padding-top: 46px; }
      h1 { font-size: clamp(3rem, 16vw, 4.6rem); }
      .actions { width: 100%; }
      .actions .button { width: 100%; }
      .phone-label { right: -8px; }
      .footer-row { align-items: flex-start; flex-direction: column; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <a class="skip" href="#conteudo">Ir para o conteúdo</a>
  <header>
    <div class="shell nav">
      <a class="brand" href="/" aria-label="EntreCenas — início">
        <img src="/midia/entrecenas-icone.svg" alt="">
        <span>EntreCenas</span>
      </a>
      <nav aria-label="Navegação principal">
        <a href="#como-funciona">Como funciona</a>
        <a href="#historias">Histórias</a>
        <a class="button small" href="/app/">Entrar agora</a>
      </nav>
    </div>
  </header>

  <main id="conteudo">
    <div class="shell hero">
      <div class="hero-copy">
        <p class="eyebrow">Histórias interativas para adultos</p>
        <h1>Você não assiste à história. <span>Você faz parte dela.</span></h1>
        <p class="lead">Escolha um card, descubra o papel reservado para você e participe diretamente de uma história de romance, tensão e desejo.</p>
        <div class="actions">
          <a class="button" href="/app/">Entrar agora</a>
          <a class="button secondary" href="/baixar">Instalar no Android</a>
        </div>
        <div class="facts" aria-label="Informações principais">
          <span>Use online ou instale no Android</span>
          <span>Experiência para maiores de 18 anos</span>
        </div>
      </div>

      <div class="phone-wrap" aria-label="Apresentação em vídeo do EntreCenas">
        <div class="phone">
          <video autoplay muted loop playsinline preload="metadata" poster="/midia/entrecenas-reel-poster.webp" aria-label="Uma personagem chega para iniciar uma história do EntreCenas">
            <source src="/midia/entrecenas-reel.mp4" type="video/mp4">
          </video>
        </div>
        <div class="phone-label">Você também é personagem</div>
      </div>
    </div>

    <section id="como-funciona">
      <div class="shell">
        <div class="section-head">
          <p class="eyebrow">Como funciona</p>
          <h2>Em poucos passos, você entra em cena.</h2>
          <p>O roteiro já tem um universo, personagens e uma situação. O seu lugar dentro dele é apresentado pelo próprio card.</p>
        </div>
        <div class="steps">
          <article class="step">
            <h3>Escolha um card</h3>
            <p>Cada card apresenta uma história, sua atmosfera e o encontro que está prestes a começar.</p>
          </article>
          <article class="step">
            <h3>Descubra seu papel</h3>
            <p>Você entra como personagem e conhece quem representa dentro daquele roteiro.</p>
          </article>
          <article class="step">
            <h3>Viva cada cena</h3>
            <p>Participe diretamente dos diálogos e acompanhe a história se desenvolver ao seu redor.</p>
          </article>
        </div>
      </div>
    </section>

    <section class="manifesto" aria-label="Proposta do EntreCenas">
      <div class="shell manifesto-grid">
        <img class="mark" src="/midia/entrecenas-icone.svg" alt="Ícone do EntreCenas">
        <blockquote>Em cada card, uma história. Em cada história, <strong>um papel para você viver.</strong></blockquote>
      </div>
    </section>

    <section id="historias">
      <div class="shell">
        <div class="section-head">
          <p class="eyebrow">Experiências</p>
          <h2>Comece com curiosidade. Aprofunde quando quiser.</h2>
        </div>
        <div class="experience-grid">
          <article class="experience">
            <div>
              <span class="tag">Degustação</span>
              <h3>Conheça o EntreCenas</h3>
              <p>Experimente a dinâmica do aplicativo em uma história envolvente que avança até o limite da sensualidade.</p>
            </div>
            <a class="button secondary" href="/app/">Começar a experiência</a>
          </article>
          <article class="experience featured">
            <div>
              <span class="tag">Histórias completas</span>
              <h3>Quer aprofundar esse encontro?</h3>
              <p>Desbloqueie novos roteiros, conheça outros personagens e descubra os papéis reservados para você.</p>
            </div>
            <a class="button" href="/app/">Conhecer as histórias</a>
          </article>
        </div>
      </div>
    </section>

    <section>
      <div class="shell faq">
        <div>
          <p class="eyebrow">Antes de entrar</p>
          <h2>Uma experiência simples e direta.</h2>
        </div>
        <div class="questions">
          <details open>
            <summary>Como eu participo da história?</summary>
            <p>O card apresenta o contexto e o papel que você assume. A partir daí, você participa diretamente das cenas e dos diálogos do roteiro.</p>
          </details>
          <details>
            <summary>Existe uma experiência de degustação?</summary>
            <p>Sim. A degustação permite conhecer a dinâmica do EntreCenas antes de acessar as histórias completas.</p>
          </details>
          <details>
            <summary>Onde o EntreCenas funciona?</summary>
            <p>Você pode usar o EntreCenas online pelo navegador. No Android, também é possível instalar o aplicativo.</p>
          </details>
        </div>
      </div>
    </section>

    <section>
      <div class="shell final-card">
        <p class="eyebrow">A próxima cena espera por você</p>
        <h2>Entre na história. Descubra o seu papel.</h2>
        <p>Entre agora pelo navegador ou instale o EntreCenas no Android.</p>
        <div class="actions">
          <a class="button" href="/app/">Entrar agora</a>
          <a class="button secondary" href="/baixar">Instalar no Android</a>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <div class="shell footer-row">
      <span>© 2026 EntreCenas</span>
      <span>Conteúdo destinado exclusivamente a maiores de 18 anos.</span>
    </div>
  </footer>
</body>
</html>
"""


def _page_headers() -> dict[str, str]:
    return {
        "Cache-Control": "public, max-age=300",
        "Content-Security-Policy": (
            "default-src 'self'; img-src 'self' data:; media-src 'self'; "
            "style-src 'self' 'unsafe-inline'; base-uri 'self'; frame-ancestors 'none'"
        ),
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }


def _media_response(path: Path, media_type: str) -> FileResponse:
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


def install(app: Any) -> Any:
    """Instala a página comercial sem alterar os contratos da API Flet."""

    if getattr(app.state, "landing_routes_installed", False):
        return app

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/conhecer", response_class=HTMLResponse, include_in_schema=False)
    def landing_page() -> HTMLResponse:
        return HTMLResponse(landing_page_html(), headers=_page_headers())

    @app.get("/midia/entrecenas-reel.mp4", include_in_schema=False)
    def landing_reel() -> FileResponse:
        return _media_response(REEL_PATH, "video/mp4")

    @app.get("/midia/entrecenas-reel-poster.webp", include_in_schema=False)
    def landing_reel_poster() -> FileResponse:
        return _media_response(REEL_POSTER_PATH, "image/webp")

    @app.get("/midia/entrecenas-icone.svg", include_in_schema=False)
    def landing_icon() -> FileResponse:
        return _media_response(BRAND_ICON_PATH, "image/svg+xml")

    app.state.landing_routes_installed = True
    return app
