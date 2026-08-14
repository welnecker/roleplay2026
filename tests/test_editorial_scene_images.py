from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from services import editorial_scene_images as scene_images
from services.editorial_scene_images import (
    load_scene_image_map,
    message_allows_beat_image,
    render_editorial_scene_image,
    resolve_editorial_scene_image,
    resolve_numbered_beat_image,
)


@pytest.mark.parametrize(
    "message",
    [
        {"automatic_bridge": True},
        {"editorial_engagement": "automatic_bridge"},
        {"editorial_state": {"facts": {"_runtime_phase": "bridge"}}},
        {"editorial_diagnostics": {"runtime_phase": "bridge"}},
    ],
)
def test_pontes_nao_disparam_imagem_do_beat(message: dict[str, object]) -> None:
    assert message_allows_beat_image(message) is False


def test_resposta_canonica_pode_exibir_imagem_do_beat() -> None:
    message = {
        "automatic_bridge": False,
        "editorial_engagement": "engaged",
        "editorial_state": {"facts": {"_runtime_phase": "canonical"}},
    }

    assert message_allows_beat_image(message) is True


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
  expanded: true
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


def test_carregador_preserva_legenda_alt_e_forca_recolhimento(tmp_path: Path) -> None:
    scene_map = load_scene_image_map(_package(tmp_path))
    image = scene_map["encontro_001"]

    assert image["caption"] == "Mary reencontra Janio."
    assert image["alt"] == "Reencontro no supermercado."
    assert image["expanded"] is False


def test_renderizacao_explicita_mantem_imagem_recolhida(monkeypatch, tmp_path: Path) -> None:
    package_root = _package(tmp_path)
    package = SimpleNamespace(root=package_root)
    observed: dict[str, object] = {}

    monkeypatch.setattr(scene_images, "find_editorial_package", lambda _package_id: package)

    @contextmanager
    def fake_expander(label: str, *, expanded: bool):
        observed["label"] = label
        observed["expanded"] = expanded
        yield

    def fake_image(path: str, *, caption: str | None, use_container_width: bool) -> None:
        observed["path"] = path
        observed["caption"] = caption
        observed["use_container_width"] = use_container_width

    monkeypatch.setattr(scene_images.st, "expander", fake_expander)
    monkeypatch.setattr(scene_images.st, "image", fake_image)

    assert render_editorial_scene_image("example.card", "reencontro_fila_001") is True
    assert observed["expanded"] is False
    assert observed["label"] == "🖼️ Mary reencontra Janio."
    assert observed["caption"] == "Mary reencontra Janio."
    assert observed["use_container_width"] is True


def test_ids_da_planilha_reutilizam_imagens_do_roteiro_original(tmp_path: Path) -> None:
    package = _package(tmp_path)
    image_dir = package / "assets" / "scenes" / "supermercado"
    (image_dir / "encontro_acidental_001.jpg").write_bytes(b"fake-image")
    with (package / "scene_images.yaml").open("a", encoding="utf-8") as target:
        target.write(
            "\nencontro_acidental_001:\n"
            "  file: assets/scenes/supermercado/encontro_acidental_001.jpg\n"
        )

    image = resolve_editorial_scene_image(package, "supermercado_001")

    assert image is not None
    assert Path(image["path"]).name == "encontro_acidental_001.jpg"


def test_imagem_ausente_falha_com_mensagem_explicita(tmp_path: Path) -> None:
    package = tmp_path / "casada_frustrada"
    package.mkdir()
    (package / "scene_images.yaml").write_text(
        "encontro_001:\n  file: assets/inexistente.jpg\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Imagem não encontrada"):
        load_scene_image_map(package)


def test_imagens_numeradas_seguem_posicao_dos_beats_nao_o_order(tmp_path: Path) -> None:
    package = tmp_path / "camilly"
    image_dir = package / "assets" / "scenes"
    image_dir.mkdir(parents=True)
    (image_dir / "camilly1.png").write_bytes(b"first")
    (image_dir / "camilly2.png").write_bytes(b"second")

    first = resolve_numbered_beat_image(
        package, "encontro_001", ["encontro_001", "encontro_009"]
    )
    second = resolve_numbered_beat_image(
        package, "encontro_009", ["encontro_001", "encontro_009"]
    )

    assert first is not None
    assert Path(first["path"]).name == "camilly1.png"
    assert second is not None
    assert Path(second["path"]).name == "camilly2.png"


def test_mapeamento_explicito_tem_prioridade_sobre_imagem_numerada(tmp_path: Path) -> None:
    package = tmp_path / "camilly"
    image_dir = package / "assets" / "scenes"
    image_dir.mkdir(parents=True)
    (image_dir / "camilly1.png").write_bytes(b"automatic")
    (image_dir / "manual.png").write_bytes(b"manual")
    (package / "scene_images.yaml").write_text(
        "encontro_001:\n  file: assets/scenes/manual.png\n",
        encoding="utf-8",
    )

    explicit = resolve_editorial_scene_image(package, "encontro_001")
    automatic = resolve_numbered_beat_image(
        package, "encontro_001", ["encontro_001"]
    )

    assert explicit is not None
    assert Path(explicit["path"]).name == "manual.png"
    assert automatic is not None
    assert Path(automatic["path"]).name == "camilly1.png"


def test_imagem_numerada_ausente_nao_quebra_o_beat(tmp_path: Path) -> None:
    package = tmp_path / "camilly"
    package.mkdir()

    assert resolve_numbered_beat_image(
        package, "encontro_004", ["encontro_001", "encontro_004"]
    ) is None
