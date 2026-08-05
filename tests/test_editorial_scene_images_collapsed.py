from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from services import editorial_scene_images as scene_images


def test_scene_image_is_always_rendered_collapsed(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "scene.jpg"
    image_path.write_bytes(b"fake")
    package = SimpleNamespace(root=tmp_path)
    observed: dict[str, object] = {}

    monkeypatch.setattr(scene_images, "find_editorial_package", lambda _package_id: package)
    monkeypatch.setattr(scene_images, "active_editorial_node_id", lambda _package_id: "beat_001")
    monkeypatch.setattr(
        scene_images,
        "resolve_editorial_scene_image",
        lambda _root, _node_id: {
            "path": image_path,
            "caption": "Cena do encontro",
            "alt": "Mary no supermercado",
            "expanded": True,
        },
    )

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

    assert scene_images.render_editorial_scene_image("example.card") is True
    assert observed["expanded"] is False
    assert observed["label"] == "🖼️ Cena do encontro"
    assert observed["path"] == str(image_path)
