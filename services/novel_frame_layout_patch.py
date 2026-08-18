from __future__ import annotations

from typing import Any

import streamlit as st

from services.novel_frame_reveal import frame_id

_installed = False
_original_button = None
_original_render_dialogue_html = None
_original_render_scene_image = None
_original_set_page_config = None
_pending_image_call: tuple[tuple[Any, ...], dict[str, Any]] | None = None
_css_injected = False

_PAGE_CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Nunito:ital,wght@0,500;0,600;0,700;0,800;1,500;1,600;1,700&display=swap");
:root{
  --novel-font:"Nunito","Avenir Next Rounded","Trebuchet MS","Segoe UI",sans-serif;
}
section[data-testid="stMain"] .block-container{
  max-width:1480px;
  padding-left:clamp(.8rem,2.2vw,2rem);
  padding-right:clamp(.8rem,2.2vw,2rem);
  font-family:var(--novel-font);
}
section[data-testid="stMain"] .block-container h1,
section[data-testid="stMain"] .block-container h2,
section[data-testid="stMain"] .block-container h3,
section[data-testid="stMain"] .block-container p,
section[data-testid="stMain"] .block-container span,
section[data-testid="stMain"] .block-container label,
section[data-testid="stMain"] .block-container button,
section[data-testid="stMain"] .block-container input,
section[data-testid="stMain"] .block-container textarea,
section[data-testid="stMain"] .block-container .novel-frame-description,
section[data-testid="stMain"] .block-container .novel-frame-card,
section[data-testid="stMain"] .block-container .dialogue-speaker,
section[data-testid="stMain"] .block-container .dialogue-speech{
  font-family:var(--novel-font) !important;
}
section[data-testid="stMain"] .block-container h1{
  font-weight:800;
  letter-spacing:.01em;
}
section[data-testid="stMain"] .block-container .novel-frame-description,
section[data-testid="stMain"] .block-container .novel-frame-card{
  font-size:1.04rem;
  font-weight:600;
  line-height:1.5;
}
@media (max-width:899px){
  section[data-testid="stMain"] .block-container{
    padding-left:.72rem;
    padding-right:.72rem;
  }
  section[data-testid="stMain"] .block-container .novel-frame-description,
  section[data-testid="stMain"] .block-container .novel-frame-card{
    font-size:1.05rem;
    line-height:1.55;
  }
}
</style>
"""


def _set_page_config_wrapper(*args: Any, **kwargs: Any):
    """Mantém a novela V2 ampla no desktop e confortável no mobile."""

    global _css_injected
    assert _original_set_page_config is not None
    kwargs = dict(kwargs)
    kwargs["layout"] = "wide"
    result = _original_set_page_config(*args, **kwargs)
    if not _css_injected:
        st.markdown(_PAGE_CSS, unsafe_allow_html=True)
        _css_injected = True
    return result


def _scene_image_wrapper(*args: Any, **kwargs: Any) -> bool:
    """Guarda a chamada da imagem até o quadro definir sua posição visual."""

    global _pending_image_call
    assert _original_render_scene_image is not None

    if bool(kwargs.get("render_memory", True)):
        return bool(_original_render_scene_image(*args, **kwargs))

    render_kwargs = dict(kwargs)
    render_kwargs["inline"] = True
    _pending_image_call = (tuple(args), render_kwargs)
    return True


def _render_pending_image() -> bool:
    global _pending_image_call
    assert _original_render_scene_image is not None
    pending = _pending_image_call
    _pending_image_call = None
    if pending is None:
        return False
    args, kwargs = pending
    return bool(_original_render_scene_image(*args, **kwargs))


def _dialogue_wrapper(
    role: str,
    content: str,
    *,
    character_name: str = "Mary",
) -> str:
    """Compõe o quadro V2 como CENA -> IMAGEM -> trilho, sem HTML fragmentado."""

    assert _original_render_dialogue_html is not None
    current_frame = frame_id(str(content or ""))
    if not current_frame:
        _render_pending_image()
        return _original_render_dialogue_html(
            role,
            content,
            character_name=character_name,
        )

    from services.novel_frame_presentation import render_frame_sections

    sections = render_frame_sections(content, character_name=character_name)
    if sections is None:
        _render_pending_image()
        return _original_render_dialogue_html(
            role,
            content,
            character_name=character_name,
        )

    description_html, track_html = sections
    if description_html:
        st.markdown(description_html, unsafe_allow_html=True)
    _render_pending_image()
    if track_html:
        st.markdown(track_html, unsafe_allow_html=True)

    # render_message() ainda executará st.markdown() sobre o retorno; vazio
    # impede duplicação do quadro já composto acima.
    return ""


def _button_wrapper(*args: Any, **kwargs: Any) -> bool:
    """Preserva a revelação incremental e mantém Avançar após o trilho."""

    assert _original_button is not None
    return bool(_original_button(*args, **kwargs))


def install() -> None:
    global _installed
    global _original_button
    global _original_render_dialogue_html
    global _original_render_scene_image
    global _original_set_page_config
    if _installed:
        return

    from services import dialogue_presentation, editorial_scene_images

    _original_button = st.button
    _original_set_page_config = st.set_page_config
    _original_render_dialogue_html = dialogue_presentation.render_dialogue_html
    _original_render_scene_image = editorial_scene_images.render_editorial_scene_image

    st.button = _button_wrapper
    st.set_page_config = _set_page_config_wrapper
    dialogue_presentation.render_dialogue_html = _dialogue_wrapper
    editorial_scene_images.render_editorial_scene_image = _scene_image_wrapper
    _installed = True


__all__ = ["install"]
