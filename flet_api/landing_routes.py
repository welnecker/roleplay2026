from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.responses import FileResponse, HTMLResponse


LANDING_MEDIA_DIR = Path(__file__).resolve().parent.parent / "static" / "landing"
REEL_PATH = LANDING_MEDIA_DIR / "entrecenas-reel.mp4"
REEL_POSTER_PATH = LANDING_MEDIA_DIR / "entrecenas-reel-poster.webp"
BRAND_ICON_PATH = Path(__file__).resolve().parent.parent / "static" / "entrecenas-icon.svg"
DEFAULT_APP_URL = "/app/"
DEFAULT_MEDIA_BASE_URL = "/midia"
DEFAULT_SITE_URL = "https://entrecenas-roleplay.com.br"
DEFAULT_CONTACT_EMAIL = "contato@entrecenas-roleplay.com.br"


def landing_page_html(
    *,
    app_url: str = DEFAULT_APP_URL,
    media_base_url: str = DEFAULT_MEDIA_BASE_URL,
    site_url: str = DEFAULT_SITE_URL,
) -> str:
    html = """<!doctype html>
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
  <meta property="og:url" content="__SITE_URL__/conhecer">
  <meta property="og:image" content="__MEDIA_BASE_URL__/landing/entrecenas-reel-poster.webp">
  <meta property="og:image:width" content="720">
  <meta property="og:image:height" content="1280">
  <link rel="canonical" href="__SITE_URL__/conhecer">
  <link rel="icon" href="__MEDIA_BASE_URL__/brand/entrecenas-icone.svg" type="image/svg+xml">
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
    .footer-links { display: flex; flex-wrap: wrap; gap: 10px 20px; }
    .footer-links a { color: var(--muted); text-decoration: none; }
    .footer-links a:hover, .footer-links a:focus-visible { color: var(--cream); text-decoration: underline; }

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
        <img src="__MEDIA_BASE_URL__/brand/entrecenas-icone.svg" alt="">
        <span>EntreCenas</span>
      </a>
      <nav aria-label="Navegação principal">
        <a href="#como-funciona">Como funciona</a>
        <a href="#historias">Histórias</a>
        <a class="button small" href="__APP_URL__">Entrar agora</a>
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
          <a class="button" href="__APP_URL__">Entrar agora</a>
        </div>
        <div class="facts" aria-label="Informações principais">
          <span>Use online pelo celular ou computador</span>
          <span>Experiência para maiores de 18 anos</span>
          <span>Pagamento único por execução, sem assinatura</span>
        </div>
      </div>

      <div class="phone-wrap" aria-label="Apresentação em vídeo do EntreCenas">
        <div class="phone">
          <video autoplay muted loop playsinline preload="metadata" poster="__MEDIA_BASE_URL__/landing/entrecenas-reel-poster.webp" aria-label="Uma personagem chega para iniciar uma história do EntreCenas">
            <source src="__MEDIA_BASE_URL__/landing/entrecenas-reel.mp4" type="video/mp4">
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
        <img class="mark" src="__MEDIA_BASE_URL__/brand/entrecenas-icone.svg" alt="Ícone do EntreCenas">
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
            <a class="button secondary" href="__APP_URL__">Começar a experiência</a>
          </article>
          <article class="experience featured">
            <div>
              <span class="tag">Histórias completas</span>
              <h3>Quer aprofundar esse encontro?</h3>
              <p>Desbloqueie novos roteiros, conheça outros personagens e descubra os papéis reservados para você.</p>
            </div>
            <a class="button" href="__APP_URL__">Conhecer as histórias</a>
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
            <p>Você pode usar o EntreCenas diretamente pelo navegador, tanto no celular quanto no computador, sem instalar nada.</p>
          </details>
          <details>
            <summary>Existe mensalidade ou assinatura?</summary>
            <p>Não. Cada pagamento é unitário e libera uma execução do card e do roteiro escolhidos. Você pode retomar essa mesma execução; uma nova execução pode exigir novo pagamento. Não existe mensalidade, assinatura, renovação automática ou cobrança recorrente.</p>
          </details>
        </div>
      </div>
    </section>

    <section>
      <div class="shell final-card">
        <p class="eyebrow">A próxima cena espera por você</p>
        <h2>Entre na história. Descubra o seu papel.</h2>
        <p>Entre agora pelo navegador, no celular ou no computador.</p>
        <div class="actions">
          <a class="button" href="__APP_URL__">Entrar agora</a>
        </div>
      </div>
    </section>
  </main>

  <footer>
    <div class="shell footer-row">
      <span>© 2026 EntreCenas</span>
      <div class="footer-links">
        <a href="/termos-de-uso/">Termos de Uso</a>
        <a href="/politica-de-privacidade/">Política de Privacidade</a>
      </div>
      <span>Conteúdo destinado exclusivamente a maiores de 18 anos.</span>
    </div>
  </footer>
</body>
</html>
"""
    return (
        html.replace("__APP_URL__", app_url.rstrip("/") + "/")
        .replace("__MEDIA_BASE_URL__", media_base_url.rstrip("/"))
        .replace("__SITE_URL__", site_url.rstrip("/"))
    )


LEGAL_PAGE_TEMPLATE = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#0c2e2d">
  <meta name="description" content="__LEGAL_DESCRIPTION__">
  <meta name="robots" content="index,follow">
  <link rel="canonical" href="__SITE_URL____LEGAL_PATH__">
  <link rel="icon" href="__MEDIA_BASE_URL__/brand/entrecenas-icone.svg" type="image/svg+xml">
  <title>__LEGAL_TITLE__ — EntreCenas</title>
  <style>
    :root { color-scheme: dark; --ink:#071918; --green:#0c2e2d; --line:#285654; --rose:#f05b91; --cream:#fff8fb; --muted:#c7d7d5; }
    * { box-sizing: border-box; }
    body { margin:0; min-width:320px; background:radial-gradient(circle at 85% 4%,rgba(210,67,105,.16),transparent 28rem),var(--ink); color:var(--cream); font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; line-height:1.7; }
    a { color:#ffabc5; }
    .shell { width:min(860px,calc(100% - 36px)); margin-inline:auto; }
    header { border-bottom:1px solid rgba(255,255,255,.08); background:rgba(7,25,24,.82); }
    .nav { min-height:72px; display:flex; align-items:center; justify-content:space-between; gap:20px; }
    .brand { display:inline-flex; align-items:center; gap:11px; color:var(--cream); text-decoration:none; font-weight:850; }
    .brand img { width:40px; height:40px; border-radius:10px; }
    .back { color:var(--muted); text-decoration:none; font-weight:700; }
    main { padding:clamp(48px,8vw,84px) 0 80px; }
    .eyebrow { color:#ffabc5; font-size:.8rem; font-weight:850; letter-spacing:.12em; text-transform:uppercase; }
    h1 { margin:10px 0 16px; font-size:clamp(2.5rem,7vw,4.5rem); line-height:1; letter-spacing:-.05em; }
    .updated { margin:0 0 38px; color:#91aaa7; }
    article { padding:clamp(24px,5vw,48px); border:1px solid var(--line); border-radius:26px; background:rgba(255,255,255,.035); }
    h2 { margin:36px 0 8px; font-size:1.35rem; line-height:1.25; }
    h2:first-child { margin-top:0; }
    p, li { color:var(--muted); }
    strong { color:var(--cream); }
    .notice { margin:24px 0; padding:18px 20px; border-left:4px solid var(--rose); border-radius:8px; background:rgba(240,91,145,.09); }
    footer { padding:28px 0 44px; color:#89a3a0; font-size:.88rem; }
    .footer-row { display:flex; flex-wrap:wrap; justify-content:space-between; gap:14px 24px; border-top:1px solid rgba(255,255,255,.08); padding-top:24px; }
    .footer-row a { color:var(--muted); }
  </style>
</head>
<body>
  <header><div class="shell nav"><a class="brand" href="/"><img src="__MEDIA_BASE_URL__/brand/entrecenas-icone.svg" alt=""><span>EntreCenas</span></a><a class="back" href="/">Voltar ao início</a></div></header>
  <main><div class="shell"><p class="eyebrow">Transparência e segurança</p><h1>__LEGAL_TITLE__</h1><p class="updated">Última atualização: 14 de setembro de 2026</p><article>__LEGAL_BODY__</article></div></main>
  <footer><div class="shell footer-row"><span>© 2026 EntreCenas</span><a href="/termos-de-uso/">Termos de Uso</a><a href="/politica-de-privacidade/">Política de Privacidade</a><span>Exclusivo para maiores de 18 anos.</span></div></footer>
</body>
</html>"""


PRIVACY_POLICY_BODY = """
<h2>1. Sobre esta política</h2>
<p>Esta Política explica como o EntreCenas trata dados pessoais ao oferecer histórias interativas para adultos. O tratamento observa a Lei Geral de Proteção de Dados Pessoais — LGPD (Lei nº 13.709/2018).</p>

<h2>2. Dados que podemos tratar</h2>
<ul>
  <li><strong>Cadastro:</strong> nome de exibição, endereço de e-mail e senha armazenada de forma protegida por hash.</li>
  <li><strong>Perfil da história:</strong> nomes escolhidos para os personagens e preferências necessárias à personalização do roteiro.</li>
  <li><strong>Uso e progresso:</strong> cards acessados, execuções, posição no roteiro, interações técnicas e estado necessário para retomar a história.</li>
  <li><strong>Compra:</strong> e-mail do pagador, card adquirido, valor, situação, identificadores da ordem e eventos de confirmação. Dados bancários e credenciais de pagamento são tratados pelo Mercado Pago.</li>
  <li><strong>Segurança e funcionamento:</strong> endereço IP, navegador, dispositivo, horários, rotas acessadas, métricas de desempenho e registros de erro, conforme disponibilizados pela infraestrutura.</li>
</ul>

<h2>3. Para que usamos os dados</h2>
<p>Usamos os dados para criar e autenticar a conta, personalizar e retomar histórias, processar pagamentos unitários, liberar o card comprado, prevenir fraude e abuso, prestar suporte, manter a segurança, cumprir obrigações legais e melhorar estabilidade e desempenho.</p>

<h2>4. Pagamento unitário</h2>
<div class="notice"><strong>O EntreCenas não oferece mensalidade ou assinatura.</strong> Cada pagamento é avulso e corresponde a uma execução do card e do roteiro escolhidos. A mesma execução pode ser retomada; uma nova execução pode exigir novo pagamento. Não há renovação automática nem cobrança recorrente.</div>

<h2>5. Compartilhamento e operadores</h2>
<p>Não vendemos dados pessoais. Podemos compartilhá-los, no limite necessário, com o <strong>Mercado Pago</strong> para processar e confirmar compras; <strong>Render</strong> para executar a aplicação e o banco operacional; <strong>Cloudflare/R2</strong> para entrega da landing page, segurança e mídia; <strong>Google Sheets</strong> como fonte editorial dos roteiros; e <strong>OpenRouter e seu provedor de modelo</strong> apenas quando algum recurso interpretativo estiver ativado. Também poderemos compartilhar dados para cumprir obrigação legal ou ordem de autoridade competente.</p>

<h2>6. Cookies e armazenamento local</h2>
<p>Utilizamos somente recursos técnicos necessários à autenticação, segurança, continuidade da sessão e funcionamento do aplicativo. Bloqueá-los no navegador pode impedir o login ou a retomada da experiência.</p>

<h2>7. Conservação</h2>
<p>Os dados são mantidos pelo período necessário às finalidades informadas, à execução do serviço, à prevenção de fraude e ao cumprimento de obrigações legais, regulatórias, fiscais ou judiciais. Quando cabível, serão eliminados ou anonimizados após o encerramento da finalidade.</p>

<h2>8. Direitos do titular</h2>
<p>Nos termos da LGPD, você pode solicitar confirmação e acesso, correção, informação sobre compartilhamentos, anonimização, bloqueio ou eliminação de dados desnecessários ou tratados em desconformidade, além dos demais direitos aplicáveis. A exclusão pode não alcançar registros que precisem ser conservados por obrigação legal ou para exercício regular de direitos.</p>

<h2>9. Segurança</h2>
<p>Adotamos conexão HTTPS, controle de acesso, senhas protegidas por hash, segregação de segredos e registros técnicos de segurança. Nenhum sistema é absolutamente imune a incidentes, mas aplicamos medidas proporcionais aos riscos e restringimos o acesso operacional.</p>

<h2>10. Conteúdo adulto e menores</h2>
<p>O EntreCenas é destinado exclusivamente a pessoas com 18 anos ou mais. Não buscamos conscientemente coletar dados de crianças ou adolescentes. Caso identifiquemos cadastro incompatível com essa regra, poderemos suspender a conta e adotar as medidas cabíveis.</p>

<h2>11. Contato</h2>
<p>Para dúvidas ou exercício de direitos relativos a dados pessoais, contate o responsável pela plataforma pelo e-mail <a href="mailto:__CONTACT_EMAIL__">__CONTACT_EMAIL__</a>.</p>
"""


TERMS_OF_USE_BODY = """
<h2>1. Aceitação e maioridade</h2>
<p>Estes Termos regem o acesso ao EntreCenas. Ao criar uma conta ou utilizar a plataforma, você declara que leu e concorda com estas condições e que possui <strong>18 anos ou mais</strong>.</p>

<h2>2. Descrição do serviço</h2>
<p>O EntreCenas oferece histórias interativas digitais em cards. Cada card apresenta um roteiro, personagens e um papel para o usuário acompanhar pelo navegador. Uma experiência de degustação pode ser disponibilizada gratuitamente e ter seu conteúdo ou disponibilidade alterados.</p>

<h2>3. Compra avulsa por card</h2>
<div class="notice"><strong>Não existe mensalidade, assinatura ou renovação automática.</strong> Cada pagamento é unitário e libera uma execução do card e do roteiro expressamente escolhidos no momento da compra. Outros cards ou novas execuções exigem pagamentos separados.</div>
<p>O preço e o conteúdo abrangido são apresentados antes da geração do Pix. O pagamento é processado pelo Mercado Pago e a execução é liberada após a confirmação. A execução já iniciada pode ser retomada pela mesma conta sem novo pagamento. A simples criação ou expiração de uma cobrança Pix não gera débito recorrente.</p>

<h2>4. Cadastro e segurança da conta</h2>
<p>Você deve informar dados válidos e manter sua senha confidencial. A conta é pessoal e não deve ser cedida ou compartilhada. Comunique imediatamente qualquer uso não autorizado pelo canal de contato informado nestes Termos.</p>

<h2>5. Acesso ao conteúdo adquirido</h2>
<p>A compra concede licença pessoal, limitada, não exclusiva e intransferível para realizar e retomar a execução adquirida do card escolhido. Após a conclusão ou consumo dessa execução, uma nova experiência do mesmo roteiro pode exigir outro pagamento unitário. A compra não transfere propriedade sobre textos, imagens, vídeos, personagens, marcas ou software. O acesso depende de conta ativa, navegador compatível e conexão à internet.</p>

<h2>6. Arrependimento, problemas e reembolso</h2>
<div class="notice"><strong>A desistência de continuar as interações não gera devolução.</strong> Depois que a execução paga do card/roteiro for liberada e iniciada, a decisão do usuário de interromper, abandonar ou não concluir a experiência não dá direito, por si só, a reembolso, total ou parcial.</div>
<p>Essa regra não elimina direitos que não possam ser afastados por contrato. Solicitações relacionadas ao direito de arrependimento quando legalmente aplicável, cobrança indevida, duplicidade, indisponibilidade ou defeito serão analisadas conforme o Código de Defesa do Consumidor e a legislação aplicável. Entre em contato pelo e-mail indicado ao final, informando o e-mail da conta e o card adquirido. Não envie senha, token ou dados bancários completos.</p>

<h2>7. Condutas proibidas</h2>
<p>É proibido tentar acessar contas ou áreas não autorizadas; fraudar pagamentos; explorar vulnerabilidades; sobrecarregar deliberadamente o serviço; automatizar acessos abusivos; copiar, redistribuir ou comercializar o conteúdo; remover avisos de autoria; ou realizar engenharia reversa em desacordo com a lei.</p>

<h2>8. Propriedade intelectual</h2>
<p>Textos, imagens, vídeos, personagens, identidade visual, marcas e código são protegidos pela legislação aplicável. O uso permitido limita-se à experiência pessoal oferecida pela plataforma.</p>

<h2>9. Suspensão</h2>
<p>Podemos restringir ou suspender contas em caso de fraude, violação destes Termos, risco à segurança, determinação legal ou uso que prejudique a plataforma ou terceiros. Sempre que possível e juridicamente adequado, serão considerados a gravidade da conduta e o direito de esclarecimento.</p>

<h2>10. Disponibilidade e responsabilidade</h2>
<p>Buscamos manter o serviço disponível e preservar compras e progresso, mas manutenções, falhas de internet, fornecedores externos ou eventos fora do controle razoável podem causar interrupções. Nada nestes Termos exclui direitos ou responsabilidades que não possam ser afastados pela legislação brasileira.</p>

<h2>11. Privacidade</h2>
<p>O tratamento de dados pessoais está descrito na <a href="/politica-de-privacidade/">Política de Privacidade</a>, que integra estes Termos.</p>

<h2>12. Alterações</h2>
<p>Estes Termos podem ser atualizados para refletir mudanças legais, operacionais ou no serviço. A versão vigente e sua data permanecerão disponíveis nesta página. Mudanças materiais serão comunicadas por meio adequado quando necessário.</p>

<h2>13. Legislação e solução de conflitos</h2>
<p>Aplicam-se as leis da República Federativa do Brasil. Fica preservado o foro legalmente competente, inclusive o foro do domicílio do consumidor quando aplicável.</p>

<h2>14. Contato</h2>
<p>Para suporte, dúvidas sobre compras ou exercício de direitos, escreva para <a href="mailto:__CONTACT_EMAIL__">__CONTACT_EMAIL__</a>.</p>
"""


def _legal_page_html(
    *,
    title: str,
    description: str,
    path: str,
    body: str,
    media_base_url: str,
    site_url: str,
    contact_email: str,
) -> str:
    return (
        LEGAL_PAGE_TEMPLATE.replace("__LEGAL_TITLE__", title)
        .replace("__LEGAL_DESCRIPTION__", description)
        .replace("__LEGAL_PATH__", path)
        .replace("__LEGAL_BODY__", body)
        .replace("__MEDIA_BASE_URL__", media_base_url.rstrip("/"))
        .replace("__SITE_URL__", site_url.rstrip("/"))
        .replace("__CONTACT_EMAIL__", contact_email.strip())
    )


def privacy_policy_html(
    *,
    media_base_url: str = DEFAULT_MEDIA_BASE_URL,
    site_url: str = DEFAULT_SITE_URL,
    contact_email: str = DEFAULT_CONTACT_EMAIL,
) -> str:
    return _legal_page_html(
        title="Política de Privacidade",
        description="Política de Privacidade do EntreCenas e informações sobre o tratamento de dados pessoais.",
        path="/politica-de-privacidade/",
        body=PRIVACY_POLICY_BODY,
        media_base_url=media_base_url,
        site_url=site_url,
        contact_email=contact_email,
    )


def terms_of_use_html(
    *,
    media_base_url: str = DEFAULT_MEDIA_BASE_URL,
    site_url: str = DEFAULT_SITE_URL,
    contact_email: str = DEFAULT_CONTACT_EMAIL,
) -> str:
    return _legal_page_html(
        title="Termos de Uso",
        description="Termos de Uso do EntreCenas, incluindo compra unitária por card e regras da plataforma.",
        path="/termos-de-uso/",
        body=TERMS_OF_USE_BODY,
        media_base_url=media_base_url,
        site_url=site_url,
        contact_email=contact_email,
    )


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

    @app.get(
        "/politica-de-privacidade",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    @app.get(
        "/politica-de-privacidade/",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def privacy_policy_page() -> HTMLResponse:
        return HTMLResponse(privacy_policy_html(), headers=_page_headers())

    @app.get(
        "/termos-de-uso",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    @app.get(
        "/termos-de-uso/",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def terms_of_use_page() -> HTMLResponse:
        return HTMLResponse(terms_of_use_html(), headers=_page_headers())

    @app.get("/midia/entrecenas-reel.mp4", include_in_schema=False)
    @app.get("/midia/landing/entrecenas-reel.mp4", include_in_schema=False)
    def landing_reel() -> FileResponse:
        return _media_response(REEL_PATH, "video/mp4")

    @app.get("/midia/entrecenas-reel-poster.webp", include_in_schema=False)
    @app.get("/midia/landing/entrecenas-reel-poster.webp", include_in_schema=False)
    def landing_reel_poster() -> FileResponse:
        return _media_response(REEL_POSTER_PATH, "image/webp")

    @app.get("/midia/entrecenas-icone.svg", include_in_schema=False)
    @app.get("/midia/brand/entrecenas-icone.svg", include_in_schema=False)
    def landing_icon() -> FileResponse:
        return _media_response(BRAND_ICON_PATH, "image/svg+xml")

    app.state.landing_routes_installed = True
    return app
