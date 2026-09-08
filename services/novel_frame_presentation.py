from __future__ import annotations

from html import escape

from services import novel_frame_patch
from services.novel_frame_reveal import (
    frame_entry_count,
    frame_id,
    normalize_frame_markers,
    reveal_frame_content,
)
from services.novel_frame_reveal_patch import reveal_index, set_current_frame


_TAIL_CLASSES = (
    "tail-left",
    "tail-center-left",
    "tail-center-right",
    "tail-right",
)


def _render_paragraphs(value: str, *, italic: bool = False) -> str:
    blocks = [block.strip() for block in str(value or "").split("\n\n") if block.strip()]
    if not blocks and str(value or "").strip():
        blocks = [str(value).strip()]
    style = "font-style:italic;" if italic else ""
    return "".join(
        f'<p style="margin:0 0 0.45rem 0;{style}">{escape(block).replace(chr(10), "<br>")}</p>'
        for block in blocks
    )


def _description_html(body: str) -> str:
    return (
        '<article class="novel-frame-description" '
        'style="padding:0.95rem 1.05rem;border-radius:14px;'
        'border:1px solid rgba(255,255,255,.18);'
        'background:#D24369;color:#fff;margin:0 0 .78rem 0;">'
        '<div style="font-size:.72rem;font-weight:700;letter-spacing:.09em;'
        'text-transform:uppercase;opacity:.82;margin-bottom:.42rem;">Cena</div>'
        f'<div style="line-height:1.48;">{_render_paragraphs(body)}</div>'
        '</article>'
    )


def _thought_card(
    actor: str,
    visible_name: str,
    body: str,
    *,
    character_name: str,
    tail_class: str,
) -> str:
    label = visible_name or actor or character_name
    return (
        f'<article class="novel-frame-card novel-frame-thought {tail_class}" '
        'style="box-sizing:border-box;padding:.8rem .9rem;border-radius:18px;'
        'border:2px dotted rgba(70,36,52,.38);'
        'background:transparent;color:#2B1822;scroll-snap-align:start;">'
        '<span class="novel-thought-tail-dot" aria-hidden="true"></span>'
        f'<div style="font-size:.72rem;font-weight:650;opacity:.68;margin-bottom:.36rem;">'
        f'✦ pensamento · {escape(label)}</div>'
        f'<div style="line-height:1.45;opacity:.92;">{_render_paragraphs(body, italic=True)}</div>'
        '</article>'
    )


def _speech_card(
    actor: str,
    visible_name: str,
    body: str,
    *,
    character_name: str,
    tail_class: str,
) -> str:
    resolved_actor, impact_balloon = novel_frame_patch._actor_balloon_directive(actor)
    is_user = novel_frame_patch._plain(resolved_actor) in {"usuario", "user", "protagonista", "voce"}
    wrapper = "dialogue-user" if is_user else "dialogue-mary"
    actor_was_used_as_label = novel_frame_patch._plain(visible_name) == novel_frame_patch._plain(actor)
    resolved_visible_name = "" if actor_was_used_as_label else visible_name
    label = resolved_visible_name or (
        "Você" if is_user else resolved_actor or character_name
    )
    impact_class = " novel-frame-impact-balloon" if impact_balloon else ""
    return (
        f'<article class="novel-frame-card novel-frame-speech dialogue-message {wrapper}{impact_class} {tail_class}" '
        'style="box-sizing:border-box;scroll-snap-align:start;margin:0;color:#2B1822;">'
        f'<div class="dialogue-speaker">{escape(label)}</div>'
        f'<div class="dialogue-speech">{novel_frame_patch._paragraphs(body)}</div>'
        '</article>'
    )


def _track_style() -> str:
    return """
<style>
.novel-frame-track{
  display:grid;
  grid-auto-flow:column;
  grid-auto-columns:calc((100% - 2.25rem)/4);
  gap:.75rem;
  overflow-x:auto;
  overscroll-behavior-inline:contain;
  scroll-snap-type:x proximity;
  padding:1.15rem .05rem .5rem .05rem;
  margin:.18rem 0 0 0;
  scrollbar-width:thin;
}
.novel-frame-track.cards-1{grid-auto-columns:100%;}
.novel-frame-track.cards-2{grid-auto-columns:calc((100% - .75rem)/2);}
.novel-frame-track.cards-3{grid-auto-columns:calc((100% - 1.5rem)/3);}
.novel-frame-track.cards-4{grid-auto-columns:calc((100% - 2.25rem)/4);}
.novel-frame-track>.novel-frame-card{
  min-width:0;
  color:#2B1822 !important;
  position:relative !important;
  overflow:visible !important;
  --tail-x:50%;
  --card-bg:#F1B5CB;
}
.novel-frame-track>.novel-frame-card.tail-left{--tail-x:16%;}
.novel-frame-track>.novel-frame-card.tail-center-left{--tail-x:36%;}
.novel-frame-track>.novel-frame-card.tail-center-right{--tail-x:64%;}
.novel-frame-track>.novel-frame-card.tail-right{--tail-x:84%;}
.novel-frame-track>.novel-frame-card:nth-child(4n+1){
  --card-bg:#ED8BAE;
  background:var(--card-bg) !important;
}
.novel-frame-track>.novel-frame-card:nth-child(4n+2){
  --card-bg:#F1B5CB;
  background:var(--card-bg) !important;
}
.novel-frame-track>.novel-frame-card:nth-child(4n+3){
  --card-bg:#F0CFDD;
  background:var(--card-bg) !important;
}
.novel-frame-track>.novel-frame-card:nth-child(4n+4){
  --card-bg:#F3D5E6;
  background:var(--card-bg) !important;
}
.novel-frame-track>.dialogue-message,
.novel-frame-track>.novel-frame-thought{
  border-color:rgba(70,36,52,.30) !important;
}
.novel-frame-track>.novel-frame-thought{
  border-style:dotted !important;
}
.novel-frame-track .dialogue-speaker,
.novel-frame-track .dialogue-speech{
  color:#2B1822 !important;
}

/* Balão editorial de impacto: ativado somente pelo sufixo de ator `_balao`. */
.novel-frame-track>.novel-frame-impact-balloon{
  border:4px solid #2B1822 !important;
  border-radius:30px 38px 28px 42px !important;
  padding:1.05rem 1.2rem 1.15rem !important;
  box-shadow:0 0 0 5px rgba(255,255,255,.96),0 13px 24px rgba(43,24,34,.28) !important;
  transform:rotate(-.35deg);
}
.novel-frame-track>.novel-frame-impact-balloon .dialogue-speaker{
  color:#2B1822 !important;
  font-size:.82rem !important;
  font-weight:900 !important;
  letter-spacing:.08em !important;
  opacity:.76;
}
.novel-frame-track>.novel-frame-impact-balloon .dialogue-speech{
  color:#2B1822 !important;
  font-size:clamp(1.45rem,2.25vw,2.15rem) !important;
  font-weight:900 !important;
  line-height:1.12 !important;
  letter-spacing:.01em;
  text-align:center;
  text-wrap:balance;
  text-shadow:1px 1px 0 rgba(255,255,255,.72);
}

/* Fala: micro-cauda triangular apontando para a imagem acima. */
.novel-frame-track>.novel-frame-speech::before{
  content:"";
  position:absolute;
  top:-9px;
  left:var(--tail-x);
  transform:translateX(-50%);
  width:0;
  height:0;
  border-left:7px solid transparent;
  border-right:7px solid transparent;
  border-bottom:10px solid var(--card-bg);
  pointer-events:none;
  z-index:2;
}
.novel-frame-track>.novel-frame-impact-balloon::before{
  top:-17px;
  border-left-width:12px;
  border-right-width:12px;
  border-bottom:18px solid #2B1822;
}
.novel-frame-track>.novel-frame-impact-balloon::after{
  content:"";
  position:absolute;
  top:-10px;
  left:var(--tail-x);
  transform:translateX(-50%);
  width:0;
  height:0;
  border-left:8px solid transparent;
  border-right:8px solid transparent;
  border-bottom:12px solid var(--card-bg);
  pointer-events:none;
  z-index:3;
}

/* Pensamento: três bolinhas pequenas subindo em direção à imagem. */
.novel-frame-track>.novel-frame-thought::before,
.novel-frame-track>.novel-frame-thought::after,
.novel-frame-track>.novel-frame-thought>.novel-thought-tail-dot{
  content:"";
  position:absolute;
  left:var(--tail-x);
  transform:translateX(-50%);
  border-radius:999px;
  background:var(--card-bg);
  border:1px solid rgba(70,36,52,.22);
  box-sizing:border-box;
  pointer-events:none;
  z-index:2;
}
.novel-frame-track>.novel-frame-thought::before{
  top:-8px;
  width:9px;
  height:9px;
}
.novel-frame-track>.novel-frame-thought::after{
  top:-16px;
  width:6px;
  height:6px;
}
.novel-frame-track>.novel-frame-thought>.novel-thought-tail-dot{
  top:-22px;
  width:4px;
  height:4px;
}

@media (max-width:899px){
  .novel-frame-track{
    grid-auto-columns:minmax(78vw,78vw);
    gap:.7rem;
    scroll-snap-type:x mandatory;
    padding-top:1.15rem;
    padding-bottom:.55rem;
  }
  .novel-frame-track.cards-2,
  .novel-frame-track.cards-3,
  .novel-frame-track.cards-4{
    grid-auto-columns:minmax(78vw,78vw);
  }
  .novel-frame-track.cards-1{grid-auto-columns:100%;}
}
</style>
"""


def render_frame_sections(content: str, *, character_name: str) -> tuple[str, str] | None:
    """Retorna CENA e trilho como dois documentos HTML independentes e fechados."""

    source = normalize_frame_markers(str(content or ""))
    current_frame_id = frame_id(source)
    entry_count = frame_entry_count(source)
    if current_frame_id:
        set_current_frame(current_frame_id, entry_count)
        source = reveal_frame_content(
            source,
            reveal_index(current_frame_id, entry_count),
        )

    parts = novel_frame_patch._parse_output(source)
    if parts is None:
        return None

    description = ""
    cards: list[str] = []
    entry_index = 0
    for kind, actor, visible_name, body in parts:
        if not body:
            continue
        if kind == "descricao":
            description = _description_html(body)
            continue

        tail_class = _TAIL_CLASSES[entry_index % len(_TAIL_CLASSES)]
        if kind == "pensamento":
            cards.append(
                _thought_card(
                    actor,
                    visible_name,
                    body,
                    character_name=character_name,
                    tail_class=tail_class,
                )
            )
            entry_index += 1
            continue
        if kind == "fala":
            cards.append(
                _speech_card(
                    actor,
                    visible_name,
                    body,
                    character_name=character_name,
                    tail_class=tail_class,
                )
            )
            entry_index += 1

    visible_columns = min(4, max(1, len(cards)))
    track = (
        _track_style()
        + f'<section class="novel-frame-track cards-{visible_columns}" '
        + 'aria-label="Falas e pensamentos do quadro">'
        + "".join(cards)
        + "</section>"
        if cards
        else ""
    )
    return description, track


def render_frame_html(content: str, *, character_name: str) -> str | None:
    """Compatibilidade: renderização fechada sem slots ou HTML partido."""

    sections = render_frame_sections(content, character_name=character_name)
    if sections is None:
        return None
    description, track = sections
    return '<section class="novel-frame-v2">' + description + track + "</section>"


def install() -> None:
    """Substitui somente a apresentação dos quadros; compilação e prompt permanecem intactos."""

    novel_frame_patch.render_frame_html = render_frame_html


__all__ = ["install", "render_frame_html", "render_frame_sections"]
