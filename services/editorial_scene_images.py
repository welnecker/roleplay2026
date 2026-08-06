from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

from services.editorial_content import find_editorial_package
from services.editorial_memory_ui import render_memory_selector


_EDITORIAL_TO_SCENE_KEY = {
    "reencontro_fila_001": "encontro_001",
    "reencontro_fila_005": "fila_005",
    "reencontro_fila_006": "fila_006",
    "reencontro_fila_007": "fila_007",
}


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


def render_editorial_scene_image(package_id: str, node_id: str) -> bool:
    """Renderiza apoio visual e a escolha explícita da próxima memória."""

    rendered = False
    package = find_editorial_package(package_id)
    if package is not None and node_id:
        image = resolve_editorial_scene_image(package.root, node_id)
        if image is not None:
            caption = str(image.get("caption", "")).strip()
            alt = str(image.get("alt", "")).strip()
            label = caption or alt or "Cena atual"
            with st.expander(f"🖼️ {label}", expanded=False):
                st.image(str(image["path"]), caption=caption or None, use_container_width=True)
            rendered = True

    render_memory_selector()
    return rendered


__all__ = ["load_scene_image_map", "render_editorial_scene_image", "resolve_editorial_scene_image"]
