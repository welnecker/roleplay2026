from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import streamlit as st
import yaml

from services.editorial_content import find_editorial_package


# O mapa visual foi criado originalmente para os IDs do motor declarativo.
# O runtime editorial usa IDs diferentes para as mesmas cenas.
_EDITORIAL_TO_SCENE_KEY = {
    "reencontro_fila_001": "encontro_001",
    "reencontro_fila_005": "fila_005",
    "reencontro_fila_006": "fila_006",
    "reencontro_fila_007": "fila_007",
}

_ORIGINAL_CAPTION_ATTR = "_roleplay_editorial_original_caption"


def load_scene_image_map(package_root: Path) -> dict[str, dict[str, object]]:
    """Lê e valida o sidecar visual sem depender do motor declarativo antigo."""

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
            "expanded": bool(value.get("expanded", False)),
        }
    return result


def resolve_editorial_scene_image(
    package_root: Path,
    node_id: str,
) -> dict[str, object] | None:
    """Resolve um beat editorial para a chave visual já existente no pacote."""

    scene_key = _EDITORIAL_TO_SCENE_KEY.get(node_id, node_id)
    return load_scene_image_map(package_root).get(scene_key)


def _active_editorial_node_id(package_id: str) -> str:
    suffix = f":{package_id}:editorial_state"
    for key, value in st.session_state.items():
        if str(key).endswith(suffix):
            return str(getattr(value, "node_id", "") or "").strip()
    return ""


def _restore_caption() -> Callable[..., Any]:
    original = getattr(st, _ORIGINAL_CAPTION_ATTR, None)
    if callable(original):
        st.caption = original
        delattr(st, _ORIGINAL_CAPTION_ATTR)
        return original
    return st.caption


def install_editorial_scene_image_hook() -> None:
    """Renderiza a imagem atual após o subtítulo do player editorial.

    O runtime é executado no momento da importação. O hook é instalado antes
    dessa importação e se remove sozinho após a segunda legenda do pacote:
    a primeira pertence à barra lateral e a segunda à área principal.
    """

    original_caption = _restore_caption()
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        return

    package = find_editorial_package(package_id)
    if package is None:
        return

    node_id = _active_editorial_node_id(package_id)
    if not node_id:
        return

    image = resolve_editorial_scene_image(package.root, node_id)
    if image is None:
        return

    expected_caption = package.manifest.card.subtitle or "História editorial"
    matching_captions = 0

    def caption_with_scene(body: object, *args: object, **kwargs: object) -> Any:
        nonlocal matching_captions
        result = original_caption(body, *args, **kwargs)
        if str(body) != expected_caption:
            return result

        matching_captions += 1
        if matching_captions != 2:
            return result

        _restore_caption()
        caption = str(image.get("caption", "")).strip()
        alt = str(image.get("alt", "")).strip()
        label = caption or alt or "Cena atual"
        with st.expander(f"🖼️ {label}", expanded=bool(image.get("expanded", False))):
            st.image(
                str(image["path"]),
                caption=caption or None,
                use_container_width=True,
            )
        return result

    setattr(st, _ORIGINAL_CAPTION_ATTR, original_caption)
    st.caption = caption_with_scene


__all__ = [
    "install_editorial_scene_image_hook",
    "load_scene_image_map",
    "resolve_editorial_scene_image",
]
