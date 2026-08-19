from __future__ import annotations

import base64
import mimetypes
from collections.abc import Mapping
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml

from services.editorial_content import find_editorial_package
from services.editorial_memory_ui import render_memory_selector


_EDITORIAL_TO_SCENE_KEY = {
    # IDs usados pelo roteiro simplificado carregado da aba ROTEIROS.
    "supermercado_001": "encontro_acidental_001",
    "supermercado_002": "encontro_acidental_002",
    "supermercado_003": "encontro_acidental_004",
    "supermercado_004": "encontro_acidental_despedida_001",
    "reencontro_fila_001": "encontro_001",
    "reencontro_fila_005": "fila_005",
    "reencontro_fila_006": "fila_006",
    "reencontro_fila_007": "fila_007",
}


def message_allows_beat_image(message: Mapping[str, object]) -> bool:
    """Retorna ``False`` para respostas de ponte que reutilizam o beat atual."""

    if bool(message.get("automatic_bridge", False)):
        return False
    if bool(message.get("decision_message", False)):
        return False
    if str(message.get("editorial_engagement", "")).strip() == "automatic_bridge":
        return False

    state = message.get("editorial_state")
    facts = state.get("facts") if isinstance(state, Mapping) else None
    phase = facts.get("_runtime_phase") if isinstance(facts, Mapping) else ""
    if str(phase or "").strip().casefold() == "bridge":
        return False

    diagnostics = message.get("editorial_diagnostics")
    diagnostic_phase = (
        diagnostics.get("runtime_phase") if isinstance(diagnostics, Mapping) else ""
    )
    return str(diagnostic_phase or "").strip().casefold() != "bridge"


def load_scene_image_map(package_root: Path) -> dict[str, dict[str, object]]:
    source = package_root / "scene_images.yaml"
    if not source.is_file():
        return {}
    raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RuntimeError(f"Mapa de imagens inválido: {source}")

    result: dict[str, dict[str, object]] = {}
    root = package_root.resolve()
    for scene_key, value in raw.items():
        if not isinstance(value, dict):
            raise RuntimeError(f"Imagem inválida para a cena {scene_key}")
        relative_file = str(value.get("file", "")).strip()
        if not relative_file:
            raise RuntimeError(f"Imagem sem arquivo para a cena {scene_key}")
        image_path = (root / relative_file).resolve()
        try:
            image_path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError(f"Imagem fora do pacote para a cena {scene_key}") from exc
        if not image_path.is_file():
            raise RuntimeError(f"Imagem não encontrada para {scene_key}: {relative_file}")
        result[str(scene_key)] = {
            "file": relative_file,
            "path": image_path,
            "caption": str(value.get("caption", "")).strip(),
            "alt": str(value.get("alt", "")).strip(),
            "expanded": False,
        }
    return result


def resolve_editorial_scene_image(package_root: Path, node_id: str) -> dict[str, object] | None:
    scene_key = _EDITORIAL_TO_SCENE_KEY.get(node_id, node_id)
    return load_scene_image_map(package_root).get(scene_key)


def resolve_numbered_beat_image(
    package_root: Path,
    node_id: str,
    ordered_beat_ids: tuple[str, ...] | list[str],
) -> dict[str, object] | None:
    """Resolve ``<pacote><posição>.<ext>`` pela ordem dos beats ativos."""

    normalized_ids = tuple(str(item or "").strip() for item in ordered_beat_ids)
    try:
        position = normalized_ids.index(str(node_id or "").strip()) + 1
    except ValueError:
        return None

    image_dir = package_root.resolve() / "assets" / "scenes"
    prefix = package_root.name.casefold()
    for extension in ("png", "jpg", "jpeg", "webp"):
        image_path = image_dir / f"{prefix}{position}.{extension}"
        if image_path.is_file():
            return {
                "file": str(image_path.relative_to(package_root.resolve())),
                "path": image_path,
                "caption": "",
                "alt": f"Imagem do beat {position}",
                "expanded": False,
            }
    return None


def image_data_uri(path: Path) -> str:
    """Converte a imagem local em data URI para o visualizador touch."""

    image_path = Path(path)
    mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    payload = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{payload}"


def zoomable_image_html(path: Path, *, caption: str = "", alt: str = "") -> str:
    """HTML autocontido com clique, duplo toque, pan e pinch-to-zoom."""

    src = image_data_uri(Path(path))
    safe_alt = escape(alt or caption or "Imagem da cena", quote=True)
    safe_caption = escape(caption)
    caption_html = (
        f'<div class="scene-caption">{safe_caption}</div>' if safe_caption else ""
    )
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5, user-scalable=yes">
<style>
html,body{{margin:0;padding:0;background:transparent;font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;}}
.scene-image-shell{{position:relative;width:100%;height:min(64vh,680px);min-height:360px;}}
.scene-thumb{{display:block;width:100%;height:100%;object-fit:contain;border-radius:14px;cursor:zoom-in;touch-action:manipulation;user-select:none;-webkit-user-drag:none;}}
.scene-hint{{position:absolute;right:10px;bottom:10px;padding:6px 9px;border-radius:999px;background:rgba(10,8,18,.76);color:#fff;font-size:12px;line-height:1;pointer-events:none;}}
.scene-caption{{position:absolute;left:10px;bottom:10px;max-width:70%;padding:6px 9px;border-radius:10px;background:rgba(10,8,18,.64);color:#fff;font-size:12px;}}
.viewer{{position:absolute;inset:0;display:none;z-index:999;background:rgba(8,5,15,.96);overflow:hidden;border-radius:14px;touch-action:none;}}
.viewer.open{{display:block;}}
.viewer-stage{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;overflow:hidden;touch-action:none;}}
.viewer-image{{max-width:96%;max-height:96%;object-fit:contain;transform-origin:center center;will-change:transform;user-select:none;-webkit-user-drag:none;touch-action:none;}}
.viewer-close,.viewer-reset{{position:absolute;z-index:1001;border:0;border-radius:999px;background:rgba(255,255,255,.14);color:#fff;backdrop-filter:blur(8px);font-weight:700;cursor:pointer;}}
.viewer-close{{right:12px;top:12px;width:38px;height:38px;font-size:22px;}}
.viewer-reset{{left:12px;top:12px;padding:10px 13px;font-size:12px;}}
@media (max-width: 899px){{.scene-image-shell{{height:min(58vh,560px);min-height:280px;}}.scene-hint{{font-size:11px;}}}}
</style>
</head>
<body>
<div class="scene-image-shell">
  <img id="thumb" class="scene-thumb" src="{src}" alt="{safe_alt}">
  <div class="scene-hint">🔍 toque para ampliar</div>
  {caption_html}
  <div id="viewer" class="viewer" aria-hidden="true">
    <button id="reset" class="viewer-reset" type="button">100%</button>
    <button id="close" class="viewer-close" type="button" aria-label="Fechar">×</button>
    <div id="stage" class="viewer-stage">
      <img id="zoomed" class="viewer-image" alt="{safe_alt}">
    </div>
  </div>
</div>
<script>
const viewer = document.getElementById('viewer');
const thumb = document.getElementById('thumb');
const zoomed = document.getElementById('zoomed');
const stage = document.getElementById('stage');
const closeBtn = document.getElementById('close');
const resetBtn = document.getElementById('reset');
let scale = 1, tx = 0, ty = 0;
let startScale = 1, startDistance = 0;
let startX = 0, startY = 0, originX = 0, originY = 0;

function clamp(v,min,max){{ return Math.max(min,Math.min(max,v)); }}
function apply(){{ zoomed.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`; }}
function reset(){{ scale=1; tx=0; ty=0; apply(); }}
function openViewer(){{ if(!zoomed.src){{ zoomed.src=thumb.src; }} reset(); viewer.classList.add('open'); viewer.setAttribute('aria-hidden','false'); }}
function closeViewer(){{ viewer.classList.remove('open'); viewer.setAttribute('aria-hidden','true'); reset(); }}
function distance(t){{ const dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY; return Math.hypot(dx,dy); }}

thumb.addEventListener('click', openViewer);
closeBtn.addEventListener('click', closeViewer);
resetBtn.addEventListener('click', reset);
zoomed.addEventListener('dblclick', (e)=>{{ e.preventDefault(); scale = scale > 1 ? 1 : 2.25; tx=0; ty=0; apply(); }});

stage.addEventListener('touchstart', (e)=>{{
  if(e.touches.length===2){{ startDistance=distance(e.touches); startScale=scale; }}
  else if(e.touches.length===1){{ startX=e.touches[0].clientX; startY=e.touches[0].clientY; originX=tx; originY=ty; }}
}}, {{passive:true}});
stage.addEventListener('touchmove', (e)=>{{
  if(e.touches.length===2){{ e.preventDefault(); scale=clamp(startScale*(distance(e.touches)/Math.max(startDistance,1)),1,5); apply(); }}
  else if(e.touches.length===1 && scale>1){{ e.preventDefault(); tx=originX+(e.touches[0].clientX-startX); ty=originY+(e.touches[0].clientY-startY); apply(); }}
}}, {{passive:false}});
stage.addEventListener('wheel', (e)=>{{ e.preventDefault(); scale=clamp(scale*(e.deltaY<0?1.15:.87),1,5); if(scale===1){{tx=0;ty=0;}} apply(); }}, {{passive:false}});
</script>
</body>
</html>"""


def render_zoomable_image(path: Path, *, caption: str = "", alt: str = "") -> None:
    """Renderiza imagem responsiva com zoom por toque/pinça ou mouse."""

    components.html(
        zoomable_image_html(Path(path), caption=caption, alt=alt),
        height=700,
        scrolling=False,
    )


def render_editorial_scene_image(
    package_id: str,
    node_id: str,
    user_id: str = "",
    *,
    render_memory: bool = True,
    ordered_beat_ids: tuple[str, ...] | list[str] = (),
    inline: bool = False,
) -> bool:
    """Renderiza a imagem do beat; ``inline=True`` a mantém aberta no painel."""

    rendered = False
    package = find_editorial_package(package_id)
    if package is not None and node_id:
        image = resolve_editorial_scene_image(package.root, node_id)
        if image is None and ordered_beat_ids:
            image = resolve_numbered_beat_image(
                package.root, node_id, ordered_beat_ids
            )
        if image is not None:
            caption = str(image.get("caption", "")).strip()
            alt = str(image.get("alt", "")).strip()
            if inline:
                render_zoomable_image(
                    Path(image["path"]),
                    caption=caption,
                    alt=alt,
                )
            else:
                label = caption or alt or "Cena atual"
                with st.expander(f"🖼️ {label}", expanded=False):
                    render_zoomable_image(
                        Path(image["path"]),
                        caption=caption,
                        alt=alt,
                    )
            rendered = True

    if render_memory:
        render_memory_selector(package_id, user_id)
    return rendered


__all__ = [
    "image_data_uri",
    "load_scene_image_map",
    "message_allows_beat_image",
    "render_editorial_scene_image",
    "render_zoomable_image",
    "resolve_editorial_scene_image",
    "resolve_numbered_beat_image",
    "zoomable_image_html",
]
