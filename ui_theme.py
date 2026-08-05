from __future__ import annotations


CARD_CSS = """
<style>
:root {
    --rp-bg-0: #09070d;
    --rp-bg-1: #120c1a;
    --rp-bg-2: #241333;
    --rp-panel: rgba(24, 16, 34, .76);
    --rp-border: rgba(206, 167, 255, .16);
    --rp-text: #f7f2ff;
    --rp-muted: #bbb1c8;
    --rp-purple-soft: #d9bdff;
    --rp-login-green: #0c2e2d;
}
html, body, [data-testid="stAppViewContainer"] {
    background:
        radial-gradient(circle at 82% 8%, rgba(116, 55, 170, .20), transparent 34%),
        radial-gradient(circle at 12% 82%, rgba(74, 35, 112, .16), transparent 38%),
        linear-gradient(145deg, var(--rp-bg-0) 0%, var(--rp-bg-1) 52%, var(--rp-bg-2) 100%);
    color: var(--rp-text);
}
[data-testid="stAppViewContainer"]:has([data-testid="stForm"] input[aria-label="E-mail"]) {
    background: var(--rp-login-green);
}
[data-testid="stAppViewContainer"]:has([data-testid="stForm"] input[aria-label="E-mail"]) [data-testid="stForm"] {
    background: rgba(8, 35, 34, .78);
    border-color: rgba(236, 229, 210, .18);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(13, 9, 19, .98), rgba(30, 17, 43, .98));
    border-right: 1px solid var(--rp-border);
}
.block-container { max-width: 1180px; padding-top: 2rem; padding-bottom: 4rem; }
.hero { padding: 1.4rem 0 1rem; }
.hero h1 { font-size: 2.5rem; margin-bottom: .3rem; }
[data-testid="stForm"] {
    border: 1px solid var(--rp-border);
    border-radius: 20px;
    padding: 1.2rem;
    background: rgba(18, 12, 26, .58);
    box-shadow: 0 16px 44px rgba(0,0,0,.20);
}
[data-testid="stChatInput"] {
    background: rgba(16, 10, 24, .88);
    border: 1px solid rgba(190, 139, 255, .22);
    border-radius: 18px;
}
.dialogue-message {
    max-width: 860px;
    margin: 0 0 1rem;
    padding: 1rem 1.1rem;
    border-radius: 20px;
    border: 1px solid var(--rp-border);
    box-shadow: 0 12px 34px rgba(0,0,0,.18);
    backdrop-filter: blur(10px);
}
.dialogue-mary {
    background: linear-gradient(135deg, rgba(31, 20, 44, .86), rgba(20, 14, 29, .72));
    margin-right: 5%;
}
.dialogue-user { background: rgba(255,255,255,.045); margin-left: 9%; }
.dialogue-speaker {
    color: var(--rp-purple-soft);
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .12em;
    text-transform: uppercase;
    margin-bottom: .65rem;
}
.dialogue-speech { color: var(--rp-text); font-size: 1rem; line-height: 1.75; }
.dialogue-speech p { margin: 0 0 .85rem; }
.dialogue-speech p:last-child { margin-bottom: 0; }
.mary-thought {
    position: relative;
    margin: .1rem 0 1rem;
    padding: .9rem 1rem .9rem 1.05rem;
    border-radius: 14px;
    border: 1px solid rgba(206, 167, 255, .20);
    border-left: 4px solid rgba(196, 139, 255, .92);
    background: linear-gradient(100deg, rgba(126, 66, 190, .25), rgba(84, 43, 125, .09));
    overflow: hidden;
}
.mary-thought-label {
    color: #d9bdff;
    font-size: .72rem;
    font-weight: 850;
    letter-spacing: .11em;
    text-transform: uppercase;
    margin-bottom: .42rem;
}
.mary-thought-copy {
    color: #eadcff;
    font-family: Georgia, "Times New Roman", serif;
    font-style: italic;
    line-height: 1.62;
}
.story-flip-shell { perspective: 1200px; margin: .25rem 0 .8rem; }
.story-flip-card {
    position: relative;
    width: 100%;
    min-height: 410px;
    transform-style: preserve-3d;
    transition: transform .62s cubic-bezier(.2,.72,.2,1);
    outline: none;
}
.story-flip-shell:hover .story-flip-card,
.story-flip-card:focus,
.story-flip-card:focus-within { transform: rotateY(180deg); }
.story-face {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 1.25rem;
    border-radius: 22px;
    border: 1px solid rgba(206, 167, 255, .18);
    backface-visibility: hidden;
    -webkit-backface-visibility: hidden;
    overflow: hidden;
    box-shadow: 0 18px 44px rgba(0,0,0,.28);
}
.story-front {
    background:
        linear-gradient(180deg, rgba(8,6,12,.04) 10%, rgba(12,8,18,.92) 85%),
        var(--cover-image, linear-gradient(145deg, #29183a, #0c0911));
    background-size: cover;
    background-position: center;
}
.story-back {
    transform: rotateY(180deg);
    justify-content: flex-start;
    overflow-y: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    background: linear-gradient(145deg, rgba(35, 21, 50, .98), rgba(12, 9, 17, .99));
}
.story-kicker { color: #c5a2ef; font-size: .76rem; letter-spacing: .10em; text-transform: uppercase; }
.story-title { color: #fff; font-size: 1.55rem; font-weight: 800; margin: .35rem 0; }
.story-subtitle { color: #dfd5e9; line-height: 1.5; }
.story-meta { color: #b6a9c4; font-size: .84rem; margin-top: .8rem; }
.story-flip-hint { margin-top: .85rem; color: #d2b5f6; font-size: .8rem; }
.story-profile-name { color: #fff; font-size: 1.45rem; font-weight: 850; margin-bottom: .9rem; }
.story-profile-section { margin-bottom: .8rem; }
.story-profile-label {
    color: #cda8fb;
    font-size: .70rem;
    font-weight: 850;
    letter-spacing: .11em;
    text-transform: uppercase;
    margin-bottom: .25rem;
}
.story-profile-copy { color: #e5dce9; font-size: .92rem; line-height: 1.48; }
.story-back-hint {
    position: sticky;
    bottom: -1.25rem;
    margin: auto -1.25rem -1.25rem;
    padding: .8rem 1.25rem 1rem;
    color: #b8a8c7;
    font-size: .76rem;
    background: linear-gradient(180deg, rgba(16, 10, 23, .12), rgba(16, 10, 23, .98) 42%);
}
@media (max-width: 760px) {
    .block-container { padding-left: 1rem; padding-right: 1rem; }
    .dialogue-mary, .dialogue-user { margin-left: 0; margin-right: 0; }
    .story-flip-card { min-height: 440px; }
}
</style>
"""