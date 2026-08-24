from __future__ import annotations

from services import novel_frame_presentation

_installed = False
_original_track_style = None

_EDITORIAL_CSS = r"""
<style>
/* Tipografia editorial dos balões: leitura de novela/HQ, não interface de escritório. */
.novel-frame-track .dialogue-speaker{
  font-family:"Trebuchet MS","Segoe UI",sans-serif !important;
  font-size:.72rem !important;
  font-weight:800 !important;
  letter-spacing:.055em !important;
  text-transform:none !important;
  margin-bottom:.42rem !important;
}
.novel-frame-track .dialogue-speech{
  font-family:"Palatino Linotype","Book Antiqua",Palatino,Georgia,"Times New Roman",serif !important;
  font-size:clamp(1.08rem,1.25vw,1.24rem) !important;
  font-weight:500 !important;
  line-height:1.48 !important;
  letter-spacing:.002em !important;
  text-align:left !important;
  text-wrap:pretty;
}
.novel-frame-track .dialogue-speech p{
  margin:0 0 .58rem 0 !important;
}
.novel-frame-track .dialogue-speech p:last-child{
  margin-bottom:0 !important;
}
.novel-frame-track>.novel-frame-thought{
  font-family:"Palatino Linotype","Book Antiqua",Palatino,Georgia,"Times New Roman",serif !important;
  font-size:1.04rem !important;
  line-height:1.52 !important;
  text-align:left !important;
}
.novel-frame-track>.novel-frame-thought>div:first-of-type{
  font-family:"Trebuchet MS","Segoe UI",sans-serif !important;
  font-size:.70rem !important;
  letter-spacing:.045em !important;
}

/* O _balao continua especial, mas com composição mais narrativa e menos cartaz. */
.novel-frame-track>.novel-frame-impact-balloon .dialogue-speaker{
  font-family:"Trebuchet MS","Segoe UI",sans-serif !important;
  font-size:.76rem !important;
  letter-spacing:.055em !important;
}
.novel-frame-track>.novel-frame-impact-balloon .dialogue-speech{
  font-family:"Trebuchet MS","Segoe UI",sans-serif !important;
  font-size:clamp(1.28rem,1.85vw,1.72rem) !important;
  font-weight:900 !important;
  line-height:1.18 !important;
  letter-spacing:.003em !important;
  text-align:left !important;
  text-wrap:pretty !important;
  text-shadow:none !important;
}

@media (max-width:899px){
  .novel-frame-track .dialogue-speech{
    font-size:1.12rem !important;
    line-height:1.5 !important;
  }
  .novel-frame-track>.novel-frame-impact-balloon .dialogue-speech{
    font-size:1.34rem !important;
    line-height:1.18 !important;
  }
}
</style>
"""


def _track_style_with_editorial_typography() -> str:
    assert _original_track_style is not None
    return _original_track_style() + _EDITORIAL_CSS


def install() -> None:
    global _installed, _original_track_style
    if _installed:
        return
    _original_track_style = novel_frame_presentation._track_style
    novel_frame_presentation._track_style = _track_style_with_editorial_typography
    _installed = True


__all__ = ["install"]
