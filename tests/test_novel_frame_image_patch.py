from __future__ import annotations

from pathlib import Path

from services import novel_frame_image_patch as image_patch


def _legacy_html(_path: Path, *, caption: str = "", alt: str = "") -> str:
    return (
        '<div class="scene-image-shell">'
        '<img class="scene-thumb">'
        '</div>'
        '<style>'
        '.scene-image-shell{position:relative;width:100%;height:min(64vh,680px);min-height:360px;}'
        '.scene-thumb{display:block;width:100%;height:100%;object-fit:contain;cursor:zoom-in;}'
        '@media (max-width: 899px){.scene-image-shell{height:min(58vh,560px);min-height:280px;}.scene-hint{font-size:11px;}}'
        '</style>'
    )


def test_html_compacto_remove_caixa_vertical_fixa(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(image_patch, "_original_zoomable_image_html", _legacy_html)
    image = tmp_path / "cena.png"
    image.write_bytes(b"png")

    html = image_patch.compact_zoomable_image_html(image)

    assert "height:min(64vh,680px);min-height:360px" not in html
    assert "height:min(58vh,560px);min-height:280px" not in html
    assert ".scene-image-shell{position:relative;width:100%;}" in html
    assert "height:auto;max-height:min(64vh,680px)" in html
    assert ".scene-thumb{max-height:min(58vh,560px);}" in html


def test_renderer_v2_usa_st_iframe_com_altura_do_conteudo(monkeypatch, tmp_path: Path) -> None:
    observed: dict[str, object] = {}
    image = tmp_path / "cena.png"
    image.write_bytes(b"png")

    monkeypatch.setattr(
        image_patch,
        "compact_zoomable_image_html",
        lambda *_args, **_kwargs: "<p>imagem</p>",
    )

    def fake_iframe(src: str, *, width: str, height: str) -> None:
        observed["src"] = src
        observed["width"] = width
        observed["height"] = height

    monkeypatch.setattr(image_patch.st, "iframe", fake_iframe)

    image_patch.render_zoomable_image(image)

    assert observed == {
        "src": "<p>imagem</p>",
        "width": "stretch",
        "height": "content",
    }
