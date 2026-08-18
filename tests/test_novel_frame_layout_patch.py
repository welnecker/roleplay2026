from __future__ import annotations

from services import novel_frame_layout_patch as layout


def test_imagem_v2_fica_aberta_e_aguarda_posicao_do_quadro(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_render(*args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return True

    monkeypatch.setattr(layout, "_original_render_scene_image", fake_render)
    monkeypatch.setattr(layout, "_pending_image_call", None)

    assert layout._scene_image_wrapper(
        "roleplay2026.camilly",
        "encontro_001",
        render_memory=False,
        ordered_beat_ids=("encontro_001",),
    ) is True

    assert observed == {}
    assert layout._pending_image_call is not None
    _args, pending_kwargs = layout._pending_image_call
    assert pending_kwargs["inline"] is True

    assert layout._render_pending_image() is True
    assert observed["kwargs"]["inline"] is True


def test_avancar_preserva_wrapper_de_revelacao(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_button(*args, **kwargs) -> bool:
        observed["button"] = (args, kwargs)
        return True

    monkeypatch.setattr(layout, "_original_button", fake_button)

    assert layout._button_wrapper("Avançar", type="primary", width="stretch") is True
    assert observed["button"] == (("Avançar",), {"type": "primary", "width": "stretch"})


def test_page_config_v2_forca_wide_e_tipografia_comic(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_config(*args, **kwargs):
        observed["config"] = kwargs
        return None

    def fake_markdown(value: str, **kwargs):
        observed["css"] = value

    monkeypatch.setattr(layout, "_original_set_page_config", fake_config)
    monkeypatch.setattr(layout.st, "markdown", fake_markdown)
    layout._css_injected = False

    layout._set_page_config_wrapper(page_title="Camilly", layout="centered")

    assert observed["config"]["layout"] == "wide"
    assert "max-width:899px" in observed["css"]
    assert '"Comic Sans MS"' in observed["css"]
    assert '"Chalkboard SE"' in observed["css"]
    assert '"Marker Felt"' in observed["css"]
    assert "--novel-font" in observed["css"]
    assert "font-family:var(--novel-font) !important" in observed["css"]
