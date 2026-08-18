from __future__ import annotations

from services import novel_frame_layout_patch as layout
from services.novel_frame_presentation import IMAGE_SLOT_MARKER


def test_layout_insere_imagem_entre_cena_e_cards(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(
        layout,
        "_original_render_dialogue_html",
        lambda role, content, character_name="Mary": (
            '<article class="novel-frame-description">Cena</article>'
            + IMAGE_SLOT_MARKER
            + '<section class="novel-frame-track">Cards</section>'
        ),
    )
    monkeypatch.setattr(layout, "frame_id", lambda _content: "encontro_001")
    monkeypatch.setattr(
        layout.st,
        "markdown",
        lambda value, unsafe_allow_html=False: events.append(str(value)),
    )
    monkeypatch.setattr(layout, "_render_pending_image", lambda: events.append("IMAGE") or True)

    result = layout._dialogue_wrapper(
        "assistant",
        "[QUADRO encontro_001]...[/QUADRO]",
        character_name="Camilly",
    )

    assert result == ""
    assert "novel-frame-description" in events[0]
    assert events[1] == "IMAGE"
    assert "novel-frame-track" in events[2]


def test_imagem_v2_e_adiada_e_forcada_inline(monkeypatch) -> None:
    observed: dict[str, object] = {}

    def fake_renderer(*args, **kwargs):
        observed["args"] = args
        observed["kwargs"] = kwargs
        return True

    monkeypatch.setattr(layout, "_original_render_scene_image", fake_renderer)
    monkeypatch.setattr(layout, "_pending_image_call", None)

    assert layout._scene_image_wrapper(
        "roleplay2026.camilly",
        "encontro_001",
        render_memory=False,
        ordered_beat_ids=("encontro_001",),
    ) is True

    assert observed == {}
    assert layout._pending_image_call is not None
    _args, kwargs = layout._pending_image_call
    assert kwargs["inline"] is True

    assert layout._render_pending_image() is True
    assert observed["kwargs"]["inline"] is True
