from __future__ import annotations

from services import novel_frame_presentation

_installed = False
_original_track_style = None

_EDITORIAL_CSS = r"""
<style>
/* Paleta progressiva dos balões. Vale tanto no trilho clássico quanto no
   carrossel sincronizado imagem+balão. */
.novel-frame-track>.novel-frame-card:nth-child(4n+1),
.sync-slide:nth-child(4n+1) .sync-card-wrap>.novel-frame-card{
  --card-bg:#ED8BAE;
  background:linear-gradient(135deg,#ED8BAE 0%,#F1A6C0 100%) !important;
}
.novel-frame-track>.novel-frame-card:nth-child(4n+2),
.sync-slide:nth-child(4n+2) .sync-card-wrap>.novel-frame-card{
  --card-bg:#F1B5CB;
  background:linear-gradient(135deg,#F1B5CB 0%,#F4C3D5 100%) !important;
}
.novel-frame-track>.novel-frame-card:nth-child(4n+3),
.sync-slide:nth-child(4n+3) .sync-card-wrap>.novel-frame-card{
  --card-bg:#F0CFDD;
  background:linear-gradient(135deg,#F0CFDD 0%,#F5DCE6 100%) !important;
}
.novel-frame-track>.novel-frame-card:nth-child(4n+4),
.sync-slide:nth-child(4n+4) .sync-card-wrap>.novel-frame-card{
  --card-bg:#F3D5E6;
  background:linear-gradient(135deg,#F3D5E6 0%,#F8E6EF 100%) !important;
}

/* Tipografia limpa e contemporânea. Evita o aspecto de redação/jornal. */
.novel-frame-track .dialogue-speaker,
.sync-card-wrap .dialogue-speaker{
  font-family:"Trebuchet MS","Segoe UI",Arial,sans-serif !important;
  font-size:.72rem !important;
  font-weight:800 !important;
  letter-spacing:.045em !important;
  text-transform:none !important;
  margin-bottom:.42rem !important;
}
.novel-frame-track .dialogue-speech,
.sync-card-wrap .dialogue-speech{
  font-family:"Trebuchet MS","Segoe UI",Arial,sans-serif !important;
  font-size:clamp(1.02rem,1.18vw,1.18rem) !important;
  font-weight:500 !important;
  line-height:1.46 !important;
  letter-spacing:.001em !important;
  text-align:left !important;
  text-wrap:pretty;
}
.novel-frame-track .dialogue-speech p,
.sync-card-wrap .dialogue-speech p{
  margin:0 0 .58rem 0 !important;
}
.novel-frame-track .dialogue-speech p:last-child,
.sync-card-wrap .dialogue-speech p:last-child{
  margin-bottom:0 !important;
}
.novel-frame-track>.novel-frame-thought,
.sync-card-wrap>.novel-frame-thought{
  font-family:"Trebuchet MS","Segoe UI",Arial,sans-serif !important;
  font-size:1.01rem !important;
  line-height:1.5 !important;
  text-align:left !important;
}
.novel-frame-track>.novel-frame-thought>div:first-of-type,
.sync-card-wrap>.novel-frame-thought>div:first-of-type{
  font-family:"Trebuchet MS","Segoe UI",Arial,sans-serif !important;
  font-size:.70rem !important;
  letter-spacing:.04em !important;
}

/* _balao: forma e tipografia deliberadamente mais fortes. O seletor inclui
   sync-card-wrap porque desktop e mobile sincronizados não ficam diretamente
   dentro de .novel-frame-track. */
.novel-frame-track>.novel-frame-impact-balloon,
.sync-card-wrap>.novel-frame-impact-balloon{
  border:4px solid #2B1822 !important;
  border-radius:30px 38px 28px 42px !important;
  padding:1.05rem 1.2rem 1.15rem !important;
  box-shadow:0 0 0 5px rgba(255,255,255,.90),0 13px 24px rgba(43,24,34,.28) !important;
  transform:rotate(-.35deg);
}
.novel-frame-track>.novel-frame-impact-balloon .dialogue-speaker,
.sync-card-wrap>.novel-frame-impact-balloon .dialogue-speaker{
  font-family:"Trebuchet MS","Segoe UI",Arial,sans-serif !important;
  font-size:.78rem !important;
  font-weight:900 !important;
  letter-spacing:.055em !important;
}
.novel-frame-track>.novel-frame-impact-balloon .dialogue-speech,
.sync-card-wrap>.novel-frame-impact-balloon .dialogue-speech{
  font-family:"Trebuchet MS","Segoe UI",Arial,sans-serif !important;
  font-size:clamp(1.62rem,2.35vw,2.28rem) !important;
  font-weight:900 !important;
  line-height:1.13 !important;
  letter-spacing:.002em !important;
  text-align:left !important;
  text-wrap:pretty !important;
  text-shadow:none !important;
}

@media (max-width:899px){
  .novel-frame-track .dialogue-speech,
  .sync-card-wrap .dialogue-speech{
    font-size:1.08rem !important;
    line-height:1.48 !important;
  }
  .novel-frame-track>.novel-frame-impact-balloon .dialogue-speech,
  .sync-card-wrap>.novel-frame-impact-balloon .dialogue-speech{
    font-size:1.62rem !important;
    line-height:1.14 !important;
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
