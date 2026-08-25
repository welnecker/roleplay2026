from __future__ import annotations

from typing import Any

from services import novel_synced_image_carousel as synced

_installed = False
_original_combined_html = None

_DESKTOP_STYLE = """
.sync-desktop-track{
  display:flex;
  align-items:flex-start;
  gap:.9rem;
  overflow-x:auto;
  overflow-y:hidden;
  scroll-snap-type:x proximity;
  overscroll-behavior-inline:contain;
  scrollbar-gutter:stable;
  padding:.15rem 0 .7rem;
  transition:height .18s ease;
}
.sync-desktop-track .sync-slide{
  flex:0 0 clamp(420px,72vw,760px);
  scroll-snap-align:start;
  padding:0 .06rem .25rem;
}
.sync-desktop-track .sync-image-wrap{
  margin-bottom:.72rem;
}
.sync-desktop-track .sync-image{
  max-height:62vh;
}
"""

_DESKTOP_AUTOSCROLL = """
<script>
(() => {
  const track = document.querySelector('.sync-desktop-track');
  if (!track) return;
  const slides = [...track.querySelectorAll('.sync-slide')];
  if (!slides.length) return;

  const scrollLatest = () => {
    const latest = Math.max(0, track.scrollWidth - track.clientWidth);
    track.scrollTo({left: latest, behavior: 'auto'});
  };

  const visibleSlideIndex = () => {
    const center = track.scrollLeft + (track.clientWidth / 2);
    let bestIndex = 0;
    let bestDistance = Number.POSITIVE_INFINITY;
    slides.forEach((slide, index) => {
      const slideCenter = slide.offsetLeft + (slide.offsetWidth / 2);
      const distance = Math.abs(slideCenter - center);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestIndex = index;
      }
    });
    return bestIndex;
  };

  const fitTrackToSlide = (index = visibleSlideIndex()) => {
    const slide = slides[Math.max(0, Math.min(slides.length - 1, index))];
    if (!slide) return;
    const styles = window.getComputedStyle(track);
    const paddingTop = Number.parseFloat(styles.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(styles.paddingBottom) || 0;
    const targetHeight = Math.ceil(slide.getBoundingClientRect().height + paddingTop + paddingBottom);
    if (targetHeight > 0) {
      track.style.height = `${targetHeight}px`;
    }
  };

  const scrollPageToCarousel = () => {
    try {
      const frame = window.frameElement;
      if (!frame) return;
      frame.scrollIntoView({behavior: 'smooth', block: 'start', inline: 'nearest'});
    } catch (_error) {
      // A rolagem vertical e apenas um aprimoramento visual. Se o navegador
      // restringir o acesso ao iframe pai, o carrossel continua funcionando.
    }
  };

  // O iframe nasce novamente a cada reveal. Posiciona o slide recém-revelado
  // como foco inicial, ajusta a altura ao conteudo realmente visivel e, uma
  // unica vez, coloca o componente no topo da viewport para leitura.
  requestAnimationFrame(() => {
    scrollLatest();
    fitTrackToSlide(slides.length - 1);
    scrollPageToCarousel();
    requestAnimationFrame(() => {
      scrollLatest();
      fitTrackToSlide(slides.length - 1);
    });
  });

  // Ao revisar slides antigos com alturas diferentes, acompanha somente a
  // altura do slide que esta efetivamente em leitura. Isso evita que um slide
  // anterior, mais alto, mantenha um grande vazio antes do botao Avancar.
  let scrollTimer = null;
  track.addEventListener('scroll', () => {
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => fitTrackToSlide(), 90);
  }, {passive:true});

  // Imagens podem terminar de carregar depois do primeiro layout e alterar
  // tanto a largura quanto a altura. Recalibra sem repetir a rolagem vertical.
  track.querySelectorAll('img').forEach((image) => {
    if (!image.complete) {
      image.addEventListener('load', () => {
        scrollLatest();
        fitTrackToSlide();
      }, {once:true});
    }
  });

  if (typeof ResizeObserver !== 'undefined') {
    const observer = new ResizeObserver(() => fitTrackToSlide());
    slides.forEach((slide) => observer.observe(slide));
  }
})();
</script>
"""


def desktop_accumulated_html(html: str) -> str:
    """Troca a apresentação desktop por uma faixa acumulativa imagem+balão.

    O mobile continua usando exatamente o carrossel já existente. No desktop,
    cada slide já revelado permanece na faixa; novos slides são acrescentados
    sem substituir os anteriores e podem ser revisitados pela rolagem horizontal.
    O foco inicial fica sempre no slide mais recente.
    """

    source = str(html or "")
    desktop_start = source.find('<section class="sync-desktop">')
    mobile_start = source.find('<section class="sync-mobile">')
    if desktop_start < 0 or mobile_start < 0 or desktop_start >= mobile_start:
        return source

    track_start = source.find('<div class="sync-mobile-track">', mobile_start)
    controls_start = source.find('<div class="sync-controls">', track_start)
    if track_start < 0 or controls_start < 0 or track_start >= controls_start:
        return source

    mobile_track = source[track_start:controls_start]
    desktop_track = mobile_track.replace(
        'class="sync-mobile-track"',
        'class="sync-desktop-track"',
        1,
    )
    desktop = f'<section class="sync-desktop">{desktop_track}</section>'
    transformed = source[:desktop_start] + desktop + source[mobile_start:]

    if _DESKTOP_STYLE not in transformed:
        transformed = transformed.replace(
            "</style>",
            _DESKTOP_STYLE + "\n</style>",
            1,
        )
    if _DESKTOP_AUTOSCROLL not in transformed:
        transformed += _DESKTOP_AUTOSCROLL
    return transformed


def _combined_html_wrapper(*args: Any, **kwargs: Any) -> str | None:
    assert _original_combined_html is not None
    html = _original_combined_html(*args, **kwargs)
    if not html:
        return html
    return desktop_accumulated_html(html)


def install() -> None:
    global _installed
    global _original_combined_html
    if _installed:
        return

    _original_combined_html = synced._combined_html
    synced._combined_html = _combined_html_wrapper
    _installed = True


__all__ = ["desktop_accumulated_html", "install"]