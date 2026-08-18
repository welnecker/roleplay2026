from __future__ import annotations

from services import novel_frame_layout_patch as layout


def test_layout_renderiza_cena_imagem_e_cards_nessa_ordem(monkeypatch) -> None:
    events: list[str] = []

    monkeypatch.setattr(layout, "frame_id", lambda _content: "encontro_001")
    monkeypatch.setattr(
        layout.st,
        "markdown",
        lambda value, unsafe_allow_html=False: events.append(str(value)),
    )
    monkeypatch.setattr(layout, "_render_pending_image", lambda: events.append("IMAGE") or True)

    from services import novel_frame_presentation

    monkeypatch.setattr(
        novel_frame_presentation,
        "render_frame_sections",
        lambda content, character_name: (
            '<article class="novel-frame-description">Cena</article>',
            '<section class="novel-frame-track">Cards</section>',
        ),
    )

    result = layout._dialogue_wrapper(
        "assistant",
        "[QUADRO encontro_001]...[/QUADRO]",
        character_name="Camilly",
    )

    assert result == ""
    assert events == [
        '<article class="novel-frame-description">Cena</article>',
        "IMAGE",
        '<section class="novel-frame-track">Cards</section>',
    ]


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
