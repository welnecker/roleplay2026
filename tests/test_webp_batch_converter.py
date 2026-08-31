from pathlib import Path

import pytest
from PIL import Image

from scripts.webp_batch_converter import conversion_plan, convert_images


def _image(path: Path, color: str = "red") -> None:
    Image.new("RGB", (32, 18), color=color).save(path)


def test_plano_ordena_naturalmente_e_renomeia_em_sequencia(tmp_path: Path) -> None:
    source = tmp_path / "originais"
    source.mkdir()
    _image(source / "foto10.png")
    _image(source / "foto2.png")
    _image(source / "foto1.png")

    plan = conversion_plan(source, tmp_path / "destino", prefix="camilly")

    assert [item.name for item, _ in plan] == ["foto1.png", "foto2.png", "foto10.png"]
    assert [target.name for _, target in plan] == [
        "camilly1.webp",
        "camilly2.webp",
        "camilly3.webp",
    ]


def test_conversao_preserva_originais_dimensoes_e_cria_destino(tmp_path: Path) -> None:
    source = tmp_path / "originais"
    source.mkdir()
    original = source / "entrada.png"
    _image(original)

    generated = convert_images(source, tmp_path / "webp", prefix="cena", quality=85)

    assert original.is_file()
    assert [path.name for path in generated] == ["cena1.webp"]
    with Image.open(generated[0]) as converted:
        assert converted.format == "WEBP"
        assert converted.size == (32, 18)


def test_conversao_nao_sobrescreve_arquivo_sem_autorizacao(tmp_path: Path) -> None:
    source = tmp_path / "originais"
    destination = tmp_path / "webp"
    source.mkdir()
    destination.mkdir()
    _image(source / "entrada.png")
    (destination / "cena1.webp").write_bytes(b"existente")

    with pytest.raises(FileExistsError, match="cena1.webp"):
        convert_images(source, destination, prefix="cena")
