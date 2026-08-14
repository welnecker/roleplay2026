from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import streamlit as st
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


def render_editorial_scene_image(
    package_id: str,
    node_id: str,
    user_id: str = "",
    *,
    render_memory: bool = True,
    ordered_beat_ids: tuple[str, ...] | list[str] = (),
) -> bool:
    """Renderiza a imagem do beat e, opcionalmente, o seletor de memória."""

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
            label = caption or alt or "Cena atual"
            with st.expander(f"🖼️ {label}", expanded=False):
                st.image(str(image["path"]), caption=caption or None, use_container_width=True)
            rendered = True

    if render_memory:
        render_memory_selector(package_id, user_id)
    return rendered


__all__ = [
    "load_scene_image_map",
    "message_allows_beat_image",
    "render_editorial_scene_image",
    "resolve_editorial_scene_image",
    "resolve_numbered_beat_image",
]
