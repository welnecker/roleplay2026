from __future__ import annotations

from typing import Any

from services import novel_synced_image_carousel as synced

_installed = False
_original_combined_html = None

_OLD_SCROLL = "slides[active]?.scrollIntoView({behavior, inline:'start', block:'nearest'});"
_NEW_SCROLL = "track.scrollTo({left: active * Math.max(track.clientWidth, 1), behavior});"


def enable_latest_slide_autoscroll(html: str) -> str:
    """Faz o carrossel mobile posicionar diretamente o slide recém-revelado."""

    source = str(html or "")
    if _OLD_SCROLL not in source:
        return source
    return source.replace(_OLD_SCROLL, _NEW_SCROLL, 1)


def _combined_html_wrapper(*args: Any, **kwargs: Any) -> str | None:
    assert _original_combined_html is not None
    html = _original_combined_html(*args, **kwargs)
    if not html:
        return html
    return enable_latest_slide_autoscroll(html)


def install() -> None:
    global _installed
    global _original_combined_html
    if _installed:
        return

    _original_combined_html = synced._combined_html
    synced._combined_html = _combined_html_wrapper
    _installed = True


__all__ = ["enable_latest_slide_autoscroll", "install"]
