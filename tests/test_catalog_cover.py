from __future__ import annotations

import base64
from pathlib import Path

from platform_core.catalog import _cover_url, cover_file_for_package


def test_capa_local_vira_data_url_utilizavel_pelo_navegador(tmp_path: Path) -> None:
    image = tmp_path / "assets" / "capas" / "capa.jpg"
    image.parent.mkdir(parents=True)
    payload = b"imagem-de-teste"
    image.write_bytes(payload)

    result = _cover_url(tmp_path, "assets/capas/capa.jpg")

    assert result.startswith("data:image/jpeg;base64,")
    encoded = result.split(",", 1)[1]
    assert base64.b64decode(encoded) == payload


def test_capa_remota_permanece_inalterada(tmp_path: Path) -> None:
    url = "https://example.com/capa.webp"

    assert _cover_url(tmp_path, url) == url


def test_capa_ausente_nao_quebra_catalogo(tmp_path: Path) -> None:
    assert _cover_url(tmp_path, "assets/capas/inexistente.jpg") == ""


def test_capa_nao_pode_sair_da_raiz_do_pacote(tmp_path: Path) -> None:
    outside = tmp_path.parent / "fora.jpg"
    outside.write_bytes(b"fora")

    assert _cover_url(tmp_path, "../fora.jpg") == ""


def test_resolve_capa_real_por_package_id_sem_base64() -> None:
    camilly = cover_file_for_package("roleplay2026.camilly")
    mary = cover_file_for_package("roleplay2026.casada_frustrada")

    assert camilly is not None and camilly.name == "capa.webp"
    assert mary is not None and mary.name == "capa1_casada.webp"
    assert cover_file_for_package("package.inexistente") is None
