from __future__ import annotations

from services.novel_frame_presentation import IMAGE_SLOT_MARKER, render_frame_html


def test_descricao_imagem_e_entries_formam_quadro_horizontal() -> None:
    content = """[QUADRO encontro_001]
[DESCRIÇÃO]
Camilly reconhece Donisete no carro.
[FALA camilly|Camilly]
Oi, Donisete!
[FALA usuario|Donisete]
Oi, Camilly... chega mais.
[PENSAMENTO camilly|Camilly]
Essa coincidência pode render.
[PENSAMENTO usuario|Donisete]
Ela está animada demais para ser só simpatia.
[/QUADRO]"""

    rendered = render_frame_html(content, character_name="Camilly")

    assert rendered is not None
    assert 'class="novel-frame-description"' in rendered
    assert '>Cena<' in rendered
    assert IMAGE_SLOT_MARKER in rendered
    assert rendered.index('class="novel-frame-description"') < rendered.index(IMAGE_SLOT_MARKER)
    assert rendered.index(IMAGE_SLOT_MARKER) < rendered.index('class="novel-frame-track"')

    assert 'grid-auto-columns:calc((100% - 2.25rem)/4)' in rendered
    assert 'grid-auto-columns:minmax(78vw,78vw)' in rendered
    assert 'overflow-x:auto' in rendered
    assert 'scroll-snap-type:x mandatory' in rendered

    assert rendered.count('class="novel-frame-card') == 4
    assert 'novel-frame-thought' in rendered
    assert 'border:2px dotted' in rendered
    assert 'font-style:italic' in rendered
    assert 'pensamento · Camilly' in rendered
    assert 'pensamento · Donisete' in rendered
    assert 'dialogue-user' in rendered
    assert 'dialogue-mary' in rendered
