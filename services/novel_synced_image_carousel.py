from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping

import streamlit as st

from services import novel_frame_patch
from services.editorial_content import find_editorial_package
from services.novel_frame_reveal import (
    frame_entry_count,
    frame_id,
    normalize_frame_markers,
    reveal_frame_content,
)
from services.novel_frame_reveal_patch import reveal_index, set_current_frame
from services.novel_frame_images import (
    clean_image_id as _clean_image_id,
    enrich_compiled_document_with_image_ids,
    image_sequence_for_frame,
)

_installed = False
_original_compile_novel_frame_story = None
_original_render_dialogue_html = None
_original_render_scene_image = None
_pending_scene_image_call: tuple[tuple[Any, ...], dict[str, Any]] | None = None


def _compile_wrapper(
    base_document: dict[str, Any],
    rows: Iterable[dict[str, Any]],
    *,
    script_version: str,
) -> dict[str, Any]:
    assert _original_compile_novel_frame_story is not None
    materialized = [dict(row) for row in rows]
    document = _original_compile_novel_frame_story(
        base_document,
        materialized,
        script_version=script_version,
    )
    return enrich_compiled_document_with_image_ids(document, materialized)


def _current_script() -> object | None:
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        return None
    suffix = f":{package_id}"
    for key, value in st.session_state.items():
        if str(key).startswith("novel_v2:script:") and str(key).endswith(suffix):
            return value
    return None


def _frame_payload(current_frame_id: str) -> dict[str, Any] | None:
    script = _current_script()
    if script is None or not current_frame_id:
        return None
    try:
        from services.novel_v2_adapter import movement_from_script

        movement = movement_from_script(script, current_frame_id)
        frame = novel_frame_patch._frame_from_movement(movement)
    except Exception:
        return None
    return dict(frame) if isinstance(frame, dict) else None


def _previous_explicit_image_id(current_frame_id: str) -> str:
    """Procura a última imagem explícita anterior no snapshot atual da sessão."""

    script = _current_script()
    if script is None:
        return ""
    beat_ids = tuple(str(item or "").strip() for item in getattr(script, "beats", ()) or ())
    if current_frame_id not in beat_ids:
        return ""
    try:
        current_index = beat_ids.index(current_frame_id)
    except ValueError:
        return ""

    from services.novel_v2_adapter import movement_from_script

    last = ""
    for beat_id in beat_ids[:current_index]:
        try:
            prior = novel_frame_patch._frame_from_movement(movement_from_script(script, beat_id))
        except Exception:
            continue
        if not isinstance(prior, dict):
            continue
        base, sequence = image_sequence_for_frame(prior, inherited_image_id=last)
        if base:
            last = base
        for image_id in sequence:
            if image_id:
                last = image_id
    return last


def _resolve_image_id(package_id: str, image_id: str) -> dict[str, object] | None:
    clean = _clean_image_id(image_id)
    if not package_id or not clean:
        return None
    package = find_editorial_package(package_id)
    if package is None:
        return None
    from services.editorial_scene_images import resolve_narrative_image_id

    return resolve_narrative_image_id(package.root, clean)


def _legacy_image_from_pending() -> dict[str, object] | None:
    pending = _pending_scene_image_call
    if pending is None:
        return None
    args, kwargs = pending
    package_id = str(args[0] if len(args) > 0 else kwargs.get("package_id", "") or "").strip()
    node_id = str(args[1] if len(args) > 1 else kwargs.get("node_id", "") or "").strip()
    if not package_id or not node_id:
        return None
    try:
        from services.editorial_scene_images import (
            resolve_editorial_scene_image,
            resolve_numbered_beat_image,
        )

        package = find_editorial_package(package_id)
        if package is None:
            return None
        image = resolve_editorial_scene_image(package.root, node_id)
        ordered = kwargs.get("ordered_beat_ids", ()) or ()
        if image is None and ordered:
            image = resolve_numbered_beat_image(package.root, node_id, ordered)
        return image
    except Exception:
        return None


def _image_src(image: Mapping[str, object] | None) -> str:
    if not image:
        return ""
    try:
        from services.editorial_scene_images import image_data_uri

        return image_data_uri(Path(image["path"]))
    except Exception:
        return ""


def _image_for_id(package_id: str, image_id: str, fallback: Mapping[str, object] | None) -> dict[str, object] | None:
    return _resolve_image_id(package_id, image_id) or (dict(fallback) if fallback else None)


def _render_card(kind: str, actor: str, visible_name: str, body: str, *, character_name: str, index: int) -> str:
    from services import novel_frame_presentation

    tail = novel_frame_presentation._TAIL_CLASSES[index % len(novel_frame_presentation._TAIL_CLASSES)]
    if kind == "pensamento":
        return novel_frame_presentation._thought_card(
            actor,
            visible_name,
            body,
            character_name=character_name,
            tail_class=tail,
        )
    return novel_frame_presentation._speech_card(
        actor,
        visible_name,
        body,
        character_name=character_name,
        tail_class=tail,
    )


def _combined_html(
    content: str,
    *,
    character_name: str,
    package_id: str,
    frame: Mapping[str, object],
    legacy_image: Mapping[str, object] | None,
) -> str | None:
    from services import novel_frame_presentation

    source = normalize_frame_markers(str(content or ""))
    current_frame_id = frame_id(source)
    count = frame_entry_count(source)
    if not current_frame_id or count <= 0:
        return None
    set_current_frame(current_frame_id, count)
    visible_count = reveal_index(current_frame_id, count)
    visible_source = reveal_frame_content(source, visible_count)
    parts = novel_frame_patch._parse_output(visible_source)
    if parts is None:
        return None

    description = ""
    cards: list[tuple[str, str, str, str]] = []
    for kind, actor, visible_name, body in parts:
        if not body:
            continue
        if kind == "descricao":
            description = novel_frame_presentation._description_html(body)
        elif kind in {"fala", "pensamento"}:
            cards.append((kind, actor, visible_name, body))

    inherited = _previous_explicit_image_id(current_frame_id)
    base_image_id, sequence = image_sequence_for_frame(frame, inherited_image_id=inherited)
    has_explicit = bool(_clean_image_id(frame.get("image_id"))) or any(
        _clean_image_id(entry.get("image_id"))
        for entry in frame.get("entries", []) or []
        if isinstance(entry, Mapping)
    )
    if not has_explicit:
        return None

    fallback_id = base_image_id
    effective_ids: list[str] = []
    for index in range(len(cards)):
        image_id = sequence[index] if index < len(sequence) else ""
        effective_ids.append(image_id or fallback_id)
        if image_id:
            fallback_id = image_id

    desktop_active_id = effective_ids[-1] if effective_ids else base_image_id
    desktop_image = _image_for_id(package_id, desktop_active_id, legacy_image)
    desktop_src = _image_src(desktop_image)

    slides: list[str] = []
    dots: list[str] = []
    for index, card in enumerate(cards):
        kind, actor, visible_name, body = card
        image = _image_for_id(
            package_id,
            effective_ids[index] if index < len(effective_ids) else "",
            legacy_image,
        )
        src = _image_src(image)
        image_html = (
            f'<div class="sync-image-wrap"><img class="sync-image" src="{src}" alt="Imagem do quadro"></div>'
            if src
            else '<div class="sync-image-wrap sync-image-empty" aria-hidden="true"></div>'
        )
        card_html = _render_card(
            kind,
            actor,
            visible_name,
            body,
            character_name=character_name,
            index=index,
        )
        slides.append(
            f'<section class="sync-slide" data-slide="{index}">{image_html}<div class="sync-card-wrap">{card_html}</div></section>'
        )
        dots.append(f'<button class="sync-dot" type="button" data-dot="{index}" aria-label="Ir ao balão {index + 1}"></button>')

    desktop_cards = "".join(
        _render_card(kind, actor, visible_name, body, character_name=character_name, index=index)
        for index, (kind, actor, visible_name, body) in enumerate(cards)
    )
    desktop_columns = min(4, max(1, len(cards)))
    desktop_track = (
        f'<section class="novel-frame-track cards-{desktop_columns}" aria-label="Falas e pensamentos do quadro">{desktop_cards}</section>'
        if desktop_cards
        else ""
    )
    desktop_image_html = (
        f'<div class="sync-desktop-image"><img src="{desktop_src}" alt="Imagem do quadro"></div>'
        if desktop_src
        else ""
    )

    styles = novel_frame_presentation._track_style() + """
<style>
.sync-mobile{display:none;}
.sync-desktop-image{width:100%;margin:.15rem 0 .25rem 0;}
.sync-desktop-image img{display:block;width:100%;height:auto;max-height:68vh;object-fit:contain;object-position:center top;border-radius:14px;}
.sync-mobile-track{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;overscroll-behavior-inline:contain;scrollbar-width:none;gap:0;}
.sync-mobile-track::-webkit-scrollbar{display:none;}
.sync-slide{flex:0 0 100%;scroll-snap-align:start;box-sizing:border-box;padding:0 .06rem .35rem;}
.sync-image-wrap{width:100%;border-radius:14px;overflow:hidden;background:rgba(20,12,22,.04);margin-bottom:.72rem;}
.sync-image{display:block;width:100%;height:auto;max-height:62vh;object-fit:contain;object-position:center top;}
.sync-image-empty{min-height:0;}
.sync-card-wrap{padding:.12rem .02rem .15rem;}
.sync-card-wrap>.novel-frame-card{width:100%;margin:0!important;position:relative!important;--tail-x:50%;--card-bg:#F1B5CB;background:#F1B5CB!important;color:#2B1822!important;}
.sync-controls{display:flex;align-items:center;justify-content:center;gap:.8rem;margin:.3rem 0 .05rem;}
.sync-arrow{border:0;border-radius:999px;width:2.25rem;height:2.25rem;background:rgba(43,24,34,.10);font-size:1.2rem;cursor:pointer;}
.sync-dots{display:flex;align-items:center;justify-content:center;gap:.34rem;min-width:3rem;}
.sync-dot{width:.44rem;height:.44rem;padding:0;border:0;border-radius:999px;background:rgba(43,24,34,.24);cursor:pointer;transition:transform .18s ease,background .18s ease;}
.sync-dot.active{background:#D24369;transform:scale(1.35);}
@media (max-width:899px){
  .sync-desktop{display:none!important;}
  .sync-mobile{display:block;}
  .novel-frame-description{margin-bottom:.72rem!important;}
}
</style>
"""
    script = """
<script>
(() => {
  const track = document.querySelector('.sync-mobile-track');
  if (!track) return;
  const slides = [...track.querySelectorAll('.sync-slide')];
  const dots = [...document.querySelectorAll('.sync-dot')];
  const prev = document.querySelector('[data-sync-prev]');
  const next = document.querySelector('[data-sync-next]');
  let active = Math.max(0, slides.length - 1);
  const setActive = (index, behavior='smooth') => {
    active = Math.max(0, Math.min(slides.length - 1, index));
    slides[active]?.scrollIntoView({behavior, inline:'start', block:'nearest'});
    dots.forEach((dot, i) => dot.classList.toggle('active', i === active));
    if (prev) prev.disabled = active === 0;
    if (next) next.disabled = active === slides.length - 1;
  };
  let timer = null;
  track.addEventListener('scroll', () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const width = Math.max(track.clientWidth, 1);
      setActive(Math.round(track.scrollLeft / width), 'auto');
    }, 80);
  }, {passive:true});
  prev?.addEventListener('click', () => setActive(active - 1));
  next?.addEventListener('click', () => setActive(active + 1));
  dots.forEach((dot, i) => dot.addEventListener('click', () => setActive(i)));
  requestAnimationFrame(() => setActive(active, 'auto'));
})();
</script>
"""
    mobile = (
        '<section class="sync-mobile">'
        f'<div class="sync-mobile-track">{"".join(slides)}</div>'
        '<div class="sync-controls">'
        '<button class="sync-arrow" type="button" data-sync-prev aria-label="Balão anterior">‹</button>'
        f'<div class="sync-dots">{"".join(dots)}</div>'
        '<button class="sync-arrow" type="button" data-sync-next aria-label="Próximo balão">›</button>'
        '</div></section>'
    )
    desktop = f'<section class="sync-desktop">{desktop_image_html}{desktop_track}</section>'
    return styles + description + desktop + mobile + script


def _scene_image_wrapper(*args: Any, **kwargs: Any) -> bool:
    global _pending_scene_image_call
    assert _original_render_scene_image is not None
    _pending_scene_image_call = (tuple(args), dict(kwargs))
    return bool(_original_render_scene_image(*args, **kwargs))


def _dialogue_wrapper(
    role: str,
    content: str,
    *,
    character_name: str = "Mary",
) -> str:
    global _pending_scene_image_call
    assert _original_render_dialogue_html is not None

    current_frame_id = frame_id(str(content or ""))
    frame = _frame_payload(current_frame_id) if current_frame_id else None
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if current_frame_id and isinstance(frame, dict):
        legacy = _legacy_image_from_pending()
        html = _combined_html(
            content,
            character_name=character_name,
            package_id=package_id,
            frame=frame,
            legacy_image=legacy,
        )
        if html:
            try:
                from services import novel_frame_layout_patch

                novel_frame_layout_patch._pending_image_call = None
            except Exception:
                pass
            _pending_scene_image_call = None
            st.iframe(html, width="stretch", height="content")
            return ""

    _pending_scene_image_call = None
    return _original_render_dialogue_html(
        role,
        content,
        character_name=character_name,
    )


def install() -> None:
    global _installed
    global _original_compile_novel_frame_story
    global _original_render_dialogue_html
    global _original_render_scene_image
    if _installed:
        return

    from services import dialogue_presentation, editorial_scene_images

    _original_compile_novel_frame_story = novel_frame_patch.compile_novel_frame_story
    _original_render_dialogue_html = dialogue_presentation.render_dialogue_html
    _original_render_scene_image = editorial_scene_images.render_editorial_scene_image

    novel_frame_patch.compile_novel_frame_story = _compile_wrapper
    dialogue_presentation.render_dialogue_html = _dialogue_wrapper
    editorial_scene_images.render_editorial_scene_image = _scene_image_wrapper
    _installed = True


__all__ = [
    "enrich_compiled_document_with_image_ids",
    "image_sequence_for_frame",
    "install",
]
