from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

from services import novel_frame_layout_patch as layout


class _Column:
    def __init__(self, name: str) -> None:
        self.name = name
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_imagem_v2_ocupa_painel_2_por_1_e_fica_aberta(monkeypatch) -> None:
    left = _Column("image")
    right = _Column("narrative")
    observed: dict[str, object] = {}

    def fake_columns(spec, **kwargs):
        observed["spec"] = spec
        observed["columns_kwargs"] = kwargs
        return left, right

    def fake_render(*args, **kwargs):
        observed["render_kwargs"] = kwargs
        return True

    monkeypatch.setattr(layout.st, "columns", fake_columns)
    monkeypatch.setattr(layout, "_original_render_scene_image", fake_render)
    layout._pending_narrative_column = None
    layout._current_narrative_column = None

    assert layout._scene_image_wrapper(
        "roleplay2026.camilly",
        "encontro_001",
        render_memory=False,
        ordered_beat_ids=("encontro_001",),
    ) is True

    assert observed["spec"] == [2, 1]
    assert observed["columns_kwargs"] == {
        "gap": "large",
        "vertical_alignment": "top",
    }
    assert observed["render_kwargs"]["inline"] is True
    assert left.entered == 1
    assert layout._pending_narrative_column is right
    assert layout._current_narrative_column is right


def test_avancar_e_renderizacao_usam_coluna_narrativa(monkeypatch) -> None:
    right = _Column("narrative")
    observed: dict[str, object] = {}

    def fake_dialogue(role: str, content: str, *, character_name: str = "Mary") -> str:
        observed["dialogue"] = (role, content, character_name)
        return "<article>quadro</article>"

    def fake_markdown(value: str, **kwargs) -> None:
        observed["markdown"] = (value, kwargs, right.entered)

    def fake_button(*args, **kwargs) -> bool:
        observed["button"] = (args, kwargs, right.entered)
        return True

    monkeypatch.setattr(layout, "_original_render_dialogue_html", fake_dialogue)
    monkeypatch.setattr(layout, "_original_button", fake_button)
    monkeypatch.setattr(layout.st, "markdown", fake_markdown)
    layout._pending_narrative_column = right
    layout._current_narrative_column = right

    content = """[QUADRO encontro_001]\n[DESCRIÇÃO]\nCena.\n[/QUADRO]"""
    assert layout._dialogue_wrapper("assistant", content, character_name="Camilly") == ""
    assert observed["markdown"][0] == "<article>quadro</article>"
    assert observed["markdown"][2] == 1

    assert layout._button_wrapper("Avançar", type="primary", width="stretch") is True
    assert observed["button"][2] == 2


def test_page_config_v2_forca_wide(monkeypatch) -> None:
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
    assert "max-width: 899px" in observed["css"]
