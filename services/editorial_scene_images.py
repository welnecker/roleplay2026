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

_ORIGINAL_CHAT_INPUT_ATTR = "_roleplay_editorial_original_chat_input"


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
        }
    return result


def resolve_editorial_scene_image(
    package_root: Path,
    node_id: str,
) -> dict[str, object] | None:
    """Resolve um beat editorial para a chave visual já existente no pacote."""

    scene_key = _EDITORIAL_TO_SCENE_KEY.get(node_id, node_id)
    return load_scene_image_map(package_root).get(scene_key)


def active_editorial_node_id(package_id: str) -> str:
    """Obtém o node_id já carregado na sessão do player editorial."""

    suffix = f":{package_id}:editorial_state"
    for key, value in st.session_state.items():
        if str(key).endswith(suffix):
            return str(getattr(value, "node_id", "") or "").strip()
    return ""


def render_editorial_scene_image(package_id: str) -> bool:
    """Renderiza a imagem do beat atual retraída por padrão."""

    package = find_editorial_package(package_id)
    if package is None:
        return False

    node_id = active_editorial_node_id(package_id)
    if not node_id:
        return False

    image = resolve_editorial_scene_image(package.root, node_id)
    if image is None:
        return False

    caption = str(image.get("caption", "")).strip()
    alt = str(image.get("alt", "")).strip()
    label = caption or alt or "Cena atual"

    # Imagens são apoio visual, não parte obrigatória do fluxo conversacional.
    # Mantê-las retraídas evita que empurrem o diálogo e a caixa de resposta para baixo.
    with st.expander(f"🖼️ {label}", expanded=False):
        st.image(
            str(image["path"]),
            caption=caption or None,
            use_container_width=True,
        )
    return True


def _restore_chat_input() -> Callable[..., Any]:
    original = getattr(st, _ORIGINAL_CHAT_INPUT_ATTR, None)
    if callable(original):
        st.chat_input = original
        delattr(st, _ORIGINAL_CHAT_INPUT_ATTR)
        return original
    return st.chat_input


def install_editorial_scene_image_hook() -> None:
    """Exibe a cena imediatamente antes da caixa de resposta.

    `st.chat_input` só é chamado depois que o runtime carregou o estado editorial,
    renderizou o cabeçalho e mostrou o histórico. Resolver a imagem nesse momento
    elimina a corrida da implementação anterior, que tentava descobrir a segunda
    chamada de `st.caption` antes de o estado estar garantidamente disponível.
    """

    original_chat_input = _restore_chat_input()
    package_id = str(st.session_state.get("selected_package_id", "") or "").strip()
    if not package_id:
        return

    def chat_input_with_scene(*args: object, **kwargs: object) -> Any:
        _restore_chat_input()
        try:
            render_editorial_scene_image(package_id)
        except Exception as exc:
            st.warning(f"Não foi possível carregar a imagem desta cena: {exc}")
        return original_chat_input(*args, **kwargs)

    setattr(st, _ORIGINAL_CHAT_INPUT_ATTR, original_chat_input)
    st.chat_input = chat_input_with_scene


__all__ = [
    "active_editorial_node_id",
    "install_editorial_scene_image_hook",
    "load_scene_image_map",
    "render_editorial_scene_image",
    "resolve_editorial_scene_image",
]
