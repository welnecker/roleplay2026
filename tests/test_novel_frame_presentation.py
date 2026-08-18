from __future__ import annotations

from services.novel_frame_presentation import render_frame_html, render_frame_sections


CONTENT = """[QUADRO encontro_001]
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


def test_cena_e_entries_sao_documentos_fechados_independentes() -> None:
    sections = render_frame_sections(CONTENT, character_name="Camilly")

    assert sections is not None
    description, track = sections
    assert 'class="novel-frame-description"' in description
    assert '>Cena<' in description
    assert "Oi, Donisete!" not in description
    assert "PENSAMENTO" not in description

    assert 'class="novel-frame-track"' in track
    assert 'grid-auto-columns:calc((100% - 2.25rem)/4)' in track
    assert 'grid-auto-columns:minmax(78vw,78vw)' in track
    assert 'overflow-x:auto' in track
    assert 'scroll-snap-type:x mandatory' in track
    assert track.count('class="novel-frame-card') == 4
    assert 'novel-frame-thought' in track
    assert 'border:2px dotted' in track
    assert 'font-style:italic' in track
    assert 'pensamento · Camilly' in track
    assert 'pensamento · Donisete' in track
    assert 'dialogue-user' in track
    assert 'dialogue-mary' in track


def test_renderizacao_de_compatibilidade_nao_contem_slot_de_imagem() -> None:
    rendered = render_frame_html(CONTENT, character_name="Camilly")

    assert rendered is not None
    assert "NOVEL_FRAME_IMAGE_SLOT" not in rendered
    assert rendered.count('<section class="novel-frame-v2">') == 1
    assert rendered.endswith("</section>")
