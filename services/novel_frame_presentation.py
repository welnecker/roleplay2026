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
        'border:1px solid rgba(127,127,127,.24);'
        'background:rgba(127,127,127,.08);margin:0 0 .78rem 0;">'
        '<div style="font-size:.72rem;font-weight:700;letter-spacing:.09em;'
        'text-transform:uppercase;opacity:.62;margin-bottom:.42rem;">Cena</div>'
        f'<div style="line-height:1.48;">{_render_paragraphs(body)}</div>'
        '</article>'
    )


def _thought_card(actor: str, visible_name: str, body: str, *, character_name: str) -> str:
    label = visible_name or actor or character_name
    return (
        '<article class="novel-frame-card novel-frame-thought" '
        'style="box-sizing:border-box;padding:.8rem .9rem;border-radius:18px;'
        'border:2px dotted rgba(127,127,127,.48);'
        'background:rgba(127,127,127,.035);scroll-snap-align:start;">'
        f'<div style="font-size:.72rem;font-weight:650;opacity:.62;margin-bottom:.36rem;">'
        f'✦ pensamento · {escape(label)}</div>'
        f'<div style="line-height:1.45;opacity:.92;">{_render_paragraphs(body, italic=True)}</div>'
        '</article>'
    )


def _speech_card(actor: str, visible_name: str, body: str, *, character_name: str) -> str:
    is_user = novel_frame_patch._plain(actor) in {"usuario", "user", "protagonista", "voce"}
    wrapper = "dialogue-user" if is_user else "dialogue-mary"
    label = visible_name or ("Você" if is_user else actor or character_name)
    return (
        f'<article class="novel-frame-card dialogue-message {wrapper}" '
        'style="box-sizing:border-box;scroll-snap-align:start;margin:0;">'
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
  padding:.12rem .05rem .5rem .05rem;
  margin:.72rem 0 0 0;
  scrollbar-width:thin;
}
.novel-frame-track>.novel-frame-card{min-width:0;}
@media (max-width:899px){
  .novel-frame-track{
    grid-auto-columns:minmax(78vw,78vw);
    gap:.7rem;
    scroll-snap-type:x mandatory;
    padding-bottom:.55rem;
  }
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
    for kind, actor, visible_name, body in parts:
        if not body:
            continue
        if kind == "descricao":
            description = _description_html(body)
            continue
        if kind == "pensamento":
            cards.append(_thought_card(actor, visible_name, body, character_name=character_name))
            continue
        if kind == "fala":
            cards.append(_speech_card(actor, visible_name, body, character_name=character_name))

    track = (
        _track_style()
        + '<section class="novel-frame-track" aria-label="Falas e pensamentos do quadro">'
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
