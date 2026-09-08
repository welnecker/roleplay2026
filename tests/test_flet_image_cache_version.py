from pathlib import Path

from flet_api.runs import FletRunService, _image_content_version


def test_versao_da_imagem_muda_quando_conteudo_e_substituido(
    tmp_path: Path,
) -> None:
    image = tmp_path / "mary5.webp"
    image.write_bytes(b"imagem antiga da mascara")
    old_version = _image_content_version({"path": image})

    image.write_bytes(b"imagem nova da porta com mary")
    new_version = _image_content_version({"path": image})

    assert len(old_version) == 16
    assert len(new_version) == 16
    assert new_version != old_version


def test_versao_da_imagem_permanece_estavel_para_o_mesmo_conteudo(
    tmp_path: Path,
) -> None:
    image = tmp_path / "mary5.webp"
    image.write_bytes(b"imagem atual")

    first = _image_content_version({"path": image})
    second = _image_content_version({"path": image})

    assert first == second


def test_url_da_imagem_inclui_versao_do_conteudo(tmp_path: Path) -> None:
    image = tmp_path / "mary5.webp"
    image.write_bytes(b"imagem atual")
    version = _image_content_version({"path": image})

    url = FletRunService._image_url(
        "roleplay2026.casada_frustrada",
        image_id="mary5.webp",
        version=version,
    )

    assert url == (
        "/api/v1/runs/image?package_id=roleplay2026.casada_frustrada"
        f"&image_id=mary5.webp&v={version}"
    )
