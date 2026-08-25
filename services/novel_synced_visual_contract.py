from __future__ import annotations

from typing import Any

from services import novel_frame_presentation as presentation
from services import novel_synced_image_carousel as synced

_installed = False
_original_track_style = None
_original_combined_html = None

_CARD_CONTRACT = """
<style>
/* Contrato visual único dos balões V2. O texto pode crescer, mas o formato-base não muda. */
.novel-frame-track>.novel-frame-card{
  box-sizing:border-box!important;
  width:100%!important;
  min-height:9.25rem;
  padding:1rem 1.05rem!important;
  border-radius:22px!important;
  border-width:1px!important;
  border-style:solid!important;
  transform:none!important;
  box-shadow:0 8px 18px rgba(43,24,34,.12)!important;
  overflow:visible!important;
}
.novel-frame-track>.novel-frame-thought{
  border-style:dotted!important;
}
.novel-frame-track>.novel-frame-impact-balloon{
  border-radius:22px!important;
  border-width:1px!important;
  padding:1rem 1.05rem!important;
  transform:none!important;
  box-shadow:0 8px 18px rgba(43,24,34,.12)!important;
}
</style>
"""

_SYNC_CONTRACT = """
<style>
/* Imagens narrativas: todas ocupam exatamente o mesmo quadro 16:9. */
.sync-image-wrap,
.sync-desktop-image{
  width:100%!important;
  aspect-ratio:16 / 9;
  border-radius:14px;
  overflow:hidden;
  background:rgba(20,12,22,.04);
}
.sync-image-wrap .sync-image,
.sync-desktop-image img{
  display:block!important;
  width:100%!important;
  height:100%!important;
  max-height:none!important;
  object-fit:cover!important;
  object-position:center center!important;
}
.sync-image-empty{aspect-ratio:auto!important;}

/* Mesmo corpo de balão no desktop e no mobile. */
.sync-card-wrap{
  padding:.78rem .02rem .15rem!important;
}
.sync-card-wrap>.novel-frame-card{
  box-sizing:border-box!important;
  width:100%!important;
  min-height:9.25rem;
  margin:0!important;
  padding:1rem 1.05rem!important;
  position:relative!important;
  overflow:visible!important;
  border-radius:22px!important;
  border:1px solid rgba(70,36,52,.30)!important;
  transform:none!important;
  box-shadow:0 8px 18px rgba(43,24,34,.12)!important;
  --tail-x:50%;
  --card-bg:#F1B5CB;
  background:var(--card-bg)!important;
  color:#2B1822!important;
}
.sync-card-wrap>.novel-frame-thought{
  border-style:dotted!important;
}
.sync-card-wrap>.novel-frame-impact-balloon{
  border-radius:22px!important;
  border-width:1px!important;
  padding:1rem 1.05rem!important;
  transform:none!important;
  box-shadow:0 8px 18px rgba(43,24,34,.12)!important;
}

/* Cauda de fala também funciona dentro de .sync-card-wrap. */
.sync-card-wrap>.novel-frame-speech::before{
  content:"";
  position:absolute;
  top:-10px;
  left:var(--tail-x);
  transform:translateX(-50%);
  width:0;
  height:0;
  border-left:8px solid transparent;
  border-right:8px solid transparent;
  border-bottom:11px solid var(--card-bg);
  pointer-events:none;
  z-index:3;
}
.sync-card-wrap>.novel-frame-impact-balloon::after{
  display:none!important;
}

/* Pensamento mantém a mesma caixa e usa a cauda de três pontos. */
.sync-card-wrap>.novel-frame-thought::before,
.sync-card-wrap>.novel-frame-thought::after,
.sync-card-wrap>.novel-frame-thought>.novel-thought-tail-dot{
  content:"";
  position:absolute;
  left:var(--tail-x);
  transform:translateX(-50%);
  border-radius:999px;
  background:var(--card-bg);
  border:1px solid rgba(70,36,52,.22);
  box-sizing:border-box;
  pointer-events:none;
  z-index:3;
}
.sync-card-wrap>.novel-frame-thought::before{top:-9px;width:9px;height:9px;}
.sync-card-wrap>.novel-frame-thought::after{top:-17px;width:6px;height:6px;}
.sync-card-wrap>.novel-frame-thought>.novel-thought-tail-dot{top:-23px;width:4px;height:4px;}
</style>
"""


def apply_visual_contract(html: str) -> str:
    source = str(html or "")
    if not source or _SYNC_CONTRACT in source:
        return source
    return source + _SYNC_CONTRACT


def _track_style_wrapper() -> str:
    assert _original_track_style is not None
    base = _original_track_style()
    if _CARD_CONTRACT in base:
        return base
    return base + _CARD_CONTRACT


def _combined_html_wrapper(*args: Any, **kwargs: Any) -> str | None:
    assert _original_combined_html is not None
    html = _original_combined_html(*args, **kwargs)
    if not html:
        return html
    return apply_visual_contract(html)


def install() -> None:
    global _installed, _original_track_style, _original_combined_html
    if _installed:
        return
    _original_track_style = presentation._track_style
    _original_combined_html = synced._combined_html
    presentation._track_style = _track_style_wrapper
    synced._combined_html = _combined_html_wrapper
    _installed = True


__all__ = ["apply_visual_contract", "install"]
