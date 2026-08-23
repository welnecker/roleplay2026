from pathlib import Path

from PIL import Image

from scripts.optimize_scene_images import optimize_scene_images


def test_otimizador_preserva_original_dimensoes_e_limite(tmp_path: Path) -> None:
    scene_dir = tmp_path / "story" / "assets" / "scenes"
    scene_dir.mkdir(parents=True)
    source = scene_dir / "story1.png"
    Image.new("RGB", (320, 180), (210, 67, 105)).save(source, "PNG")
    original_bytes = source.read_bytes()

    generated = optimize_scene_images(scene_dir, quality=98, max_bytes=500 * 1024)

    assert generated == [scene_dir / "story1.webp"]
    assert source.read_bytes() == original_bytes
    assert generated[0].stat().st_size <= 500 * 1024
    with Image.open(generated[0]) as image:
        assert image.size == (320, 180)
