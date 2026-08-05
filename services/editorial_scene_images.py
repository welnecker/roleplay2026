from __future__ import annotations

from pathlib import Path

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
            # O campo é preservado por compatibilidade, mas a interface nunca
            # abre a imagem automaticamente.
            "expanded": False,
        }
    return result


def resolve_editorial_scene_image(
    package_root: Path,
    node_id: str,
) -> dict[str, object] | None:
    """Resolve um beat editorial para a chave visual já existente no pacote."""

    scene_key = _EDITORIAL_TO_SCENE_KEY.get(node_id, node_id)
    return load_scene_image_map(package_root).get(scene_key)


def render_editorial_scene_image(package_id: str, node_id: str) -> bool:
    """Renderiza explicitamente a imagem do beat, sempre recolhida."""

    package = find_editorial_package(package_id)
    if package is None or not node_id:
        return False

    image = resolve_editorial_scene_image(package.root, node_id)
    if image is None:
        return False

    caption = str(image.get("caption", "")).strip()
    alt = str(image.get("alt", "")).strip()
    label = caption or alt or "Cena atual"
    with st.expander(f"🖼️ {label}", expanded=False):
        st.image(
            str(image["path"]),
            caption=caption or None,
            use_container_width=True,
        )
    return True


__all__ = [
    "load_scene_image_map",
    "render_editorial_scene_image",
    "resolve_editorial_scene_image",
]
