from __future__ import annotations

from pathlib import Path

import streamlit as st

from services import editorial_scene_images

_installed = False
_original_zoomable_image_html = None


def compact_zoomable_image_html(
    path: Path,
    *,
    caption: str = "",
    alt: str = "",
) -> str:
    """Mantém o zoom V2 usando a proporção natural da imagem no quadro."""

    assert _original_zoomable_image_html is not None
    html = _original_zoomable_image_html(
        Path(path),
        caption=caption,
        alt=alt,
    )
    html = html.replace(
        ".scene-image-shell{position:relative;width:100%;height:min(64vh,680px);min-height:360px;}",
        ".scene-image-shell{position:relative;width:100%;}",
    )
    html = html.replace(
        ".scene-thumb{display:block;width:100%;height:100%;object-fit:contain;",
        ".scene-thumb{display:block;width:100%;max-width:100%;height:auto;object-fit:contain;object-position:center top;",
    )
    html = html.replace(
        "@media (max-width: 899px){.scene-image-shell{height:min(58vh,560px);min-height:280px;}.scene-hint{font-size:11px;}}",
        "@media (max-width: 899px){.scene-hint{font-size:11px;}}",
    )
    return html


def render_zoomable_image(
    path: Path,
    *,
    caption: str = "",
    alt: str = "",
) -> None:
    """Renderiza o zoom V2 com altura derivada da proporção real da imagem."""

    st.iframe(
        compact_zoomable_image_html(Path(path), caption=caption, alt=alt),
        width="stretch",
        height="content",
    )


def install() -> None:
    global _installed, _original_zoomable_image_html
    if _installed:
        return

    _original_zoomable_image_html = editorial_scene_images.zoomable_image_html
    editorial_scene_images.zoomable_image_html = compact_zoomable_image_html
    editorial_scene_images.render_zoomable_image = render_zoomable_image
    _installed = True


__all__ = ["compact_zoomable_image_html", "install", "render_zoomable_image"]
