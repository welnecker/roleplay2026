from __future__ import annotations

from pathlib import Path

import pytest

from services import editorial_scene_images as scene_images
from services.editorial_scene_images import (
    load_scene_image_map,
    resolve_editorial_scene_image,
)


def _package(tmp_path: Path) -> Path:
    package = tmp_path / "casada_frustrada"
    image_dir = package / "assets" / "scenes" / "supermercado"
    image_dir.mkdir(parents=True)
    for name in (
        "reencontro_fila_001.jpg",
        "reencontro_fila_005.jpg",
        "reencontro_fila_006.jpg",
        "reencontro_fila_007.jpg",
    ):
        (image_dir / name).write_bytes(b"fake-image")

    (package / "scene_images.yaml").write_text(
        """
encontro_001:
  file: assets/scenes/supermercado/reencontro_fila_001.jpg
  caption: Mary reencontra Janio.
  alt: Reencontro no supermercado.
  expanded: false
fila_005:
  file: assets/scenes/supermercado/reencontro_fila_005.jpg
fila_006:
  file: assets/scenes/supermercado/reencontro_fila_006.jpg
fila_007:
  file: assets/scenes/supermercado/reencontro_fila_007.jpg
""".strip(),
        encoding="utf-8",
    )
    return package


def test_mapa_visual_existente_resolve_ids_do_runtime_editorial(tmp_path: Path) -> None:
    package = _package(tmp_path)

    expected = {
        "reencontro_fila_001": "reencontro_fila_001.jpg",
        "reencontro_fila_005": "reencontro_fila_005.jpg",
        "reencontro_fila_006": "reencontro_fila_006.jpg",
        "reencontro_fila_007": "reencontro_fila_007.jpg",
    }
    for node_id, filename in expected.items():
        image = resolve_editorial_scene_image(package, node_id)
        assert image is not None
        assert Path(image["path"]).name == filename


def test_carregador_preserva_legenda_alt_e_expansao(tmp_path: Path) -> None:
    scene_map = load_scene_image_map(_package(tmp_path))
    image = scene_map["encontro_001"]

    assert image["caption"] == "Mary reencontra Janio."
    assert image["alt"] == "Reencontro no supermercado."
    assert image["expanded"] is False


def test_imagem_ausente_falha_com_mensagem_explicita(tmp_path: Path) -> None:
    package = tmp_path / "casada_frustrada"
    package.mkdir()
    (package / "scene_images.yaml").write_text(
        "encontro_001:\n  file: assets/inexistente.jpg\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Imagem não encontrada"):
        load_scene_image_map(package)


def test_hook_delega_ao_chat_input_original_sem_substitui_lo_durante_a_chamada(monkeypatch) -> None:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def original(*args: object, **kwargs: object) -> str:
        calls.append((args, kwargs))
        return "mensagem enviada"

    monkeypatch.delattr(scene_images.st, scene_images._ORIGINAL_CHAT_INPUT_ATTR, raising=False)
    monkeypatch.setattr(scene_images.st, "chat_input", original)
    monkeypatch.setattr(
        scene_images.st,
        "session_state",
        {"selected_package_id": "example.card"},
    )
    monkeypatch.setattr(scene_images, "render_editorial_scene_image", lambda package_id: True)

    scene_images.install_editorial_scene_image_hook()
    wrapped = scene_images.st.chat_input

    result = wrapped("Responda", key="prompt")

    assert result == "mensagem enviada"
    assert calls == [(('Responda',), {"key": "prompt"})]
    assert scene_images.st.chat_input is wrapped
    assert getattr(scene_images.st, scene_images._ORIGINAL_CHAT_INPUT_ATTR) is original
