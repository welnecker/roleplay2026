from __future__ import annotations

from typing import Any

import streamlit as st

from services.novel_frame_reveal import frame_id

_installed = False
_original_button = None
_original_render_dialogue_html = None
_original_render_scene_image = None
_original_set_page_config = None
_pending_narrative_column = None
_current_narrative_column = None
_css_injected = False

_MOBILE_CSS = """
<style>
@media (max-width: 899px) {
  section[data-testid="stMain"] [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap !important;
    gap: .8rem !important;
  }
  section[data-testid="stMain"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
    flex: 1 1 100% !important;
    width: 100% !important;
    min-width: 100% !important;
  }
}
</style>
"""


def _set_page_config_wrapper(*args: Any, **kwargs: Any):
    """Mantém a novela V2 ampla no desktop e injeta empilhamento no mobile."""

    global _css_injected
    assert _original_set_page_config is not None
    kwargs = dict(kwargs)
    kwargs["layout"] = "wide"
    result = _original_set_page_config(*args, **kwargs)
    if not _css_injected:
        st.markdown(_MOBILE_CSS, unsafe_allow_html=True)
        _css_injected = True
    return result


def _scene_image_wrapper(*args: Any, **kwargs: Any) -> bool:
    """Abre um painel 2:1 e mantém a imagem sempre visível à esquerda."""

    global _pending_narrative_column, _current_narrative_column
    assert _original_render_scene_image is not None

    # O player V2 chama as imagens com render_memory=False. Outros usos do
    # renderer continuam com o comportamento legado e não recebem este layout.
    if bool(kwargs.get("render_memory", True)):
        return bool(_original_render_scene_image(*args, **kwargs))

    image_column, narrative_column = st.columns(
        [2, 1],
        gap="large",
        vertical_alignment="top",
    )
    render_kwargs = dict(kwargs)
    render_kwargs["inline"] = True
    with image_column:
        rendered = bool(_original_render_scene_image(*args, **render_kwargs))

    _pending_narrative_column = narrative_column
    _current_narrative_column = narrative_column
    return rendered


def _dialogue_wrapper(
    role: str,
    content: str,
    *,
    character_name: str = "Mary",
) -> str:
    """Envia quadros V2 para a terceira coluna criada pelo renderer da imagem."""

    global _pending_narrative_column, _current_narrative_column
    assert _original_render_dialogue_html is not None

    rendered = _original_render_dialogue_html(
        role,
        content,
        character_name=character_name,
    )
    current_frame = frame_id(str(content or ""))
    target = _pending_narrative_column
    if current_frame and target is not None:
        with target:
            st.markdown(rendered, unsafe_allow_html=True)
        _pending_narrative_column = None
        _current_narrative_column = target
        # O runtime ainda chamará st.markdown() com o retorno. Uma string vazia
        # evita duplicar o quadro fora da coluna sem alterar seu contrato.
        return ""
    return rendered


def _button_wrapper(*args: Any, **kwargs: Any) -> bool:
    """Mantém Avançar no rodapé da coluna narrativa atual."""

    assert _original_button is not None
    label = str(args[0] if args else kwargs.get("label", "") or "").strip()
    if label == "Avançar" and _current_narrative_column is not None:
        with _current_narrative_column:
            return bool(_original_button(*args, **kwargs))
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

    # Instalar este patch depois do reveal patch é intencional: ao capturar
    # st.button aqui, _original_button já contém a lógica que revela uma entry
    # por clique. O layout só decide onde o botão aparece.
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
