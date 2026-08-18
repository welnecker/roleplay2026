from __future__ import annotations

from html import escape

from services import novel_frame_patch
from services.novel_frame_reveal import frame_entry_count, frame_id, reveal_frame_content
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


def render_frame_html(content: str, *, character_name: str) -> str | None:
    source = str(content or "")
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

    html: list[str] = [
        '<section class="novel-frame-v2" style="display:flex;flex-direction:column;gap:0.72rem;">'
    ]
    for kind, actor, visible_name, body in parts:
        if not body:
            continue

        if kind == "descricao":
            html.append(
                '<article class="novel-frame-description" '
                'style="padding:0.9rem 1rem;border-radius:14px;'
                'border:1px solid rgba(127,127,127,.24);'
                'background:rgba(127,127,127,.08);">'
                '<div style="font-size:.72rem;font-weight:700;letter-spacing:.09em;'
                'text-transform:uppercase;opacity:.62;margin-bottom:.42rem;">Cena</div>'
                f'<div style="line-height:1.48;">{_render_paragraphs(body)}</div>'
                '</article>'
            )
            continue

        if kind == "pensamento":
            label = visible_name or actor or character_name
            html.append(
                '<article class="novel-frame-thought" '
                'style="padding:0.72rem 0.88rem;border-radius:18px;'
                'border:2px dotted rgba(127,127,127,.48);'
                'background:rgba(127,127,127,.035);margin-left:0.35rem;">'
                f'<div style="font-size:.72rem;font-weight:650;opacity:.62;margin-bottom:.32rem;">'
                f'✦ pensamento · {escape(label)}</div>'
                f'<div style="line-height:1.45;opacity:.92;">{_render_paragraphs(body, italic=True)}</div>'
                '</article>'
            )
            continue

        if kind == "fala":
            is_user = novel_frame_patch._plain(actor) in {"usuario", "user", "protagonista", "voce"}
            wrapper = "dialogue-message dialogue-user" if is_user else "dialogue-message dialogue-mary"
            label = visible_name or ("Você" if is_user else actor or character_name)
            html.append(
                f'<article class="{wrapper}">'
                f'<div class="dialogue-speaker">{escape(label)}</div>'
                f'<div class="dialogue-speech">{novel_frame_patch._paragraphs(body)}</div>'
                '</article>'
            )

    html.append("</section>")
    return "".join(html)


def install() -> None:
    """Substitui somente a apresentação dos quadros; compilação e prompt permanecem intactos."""

    novel_frame_patch.render_frame_html = render_frame_html


__all__ = ["install", "render_frame_html"]
