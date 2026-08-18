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
    assert "background:#D24369" in description
    assert "color:#fff" in description

    assert 'class="novel-frame-track"' in track
    assert 'grid-auto-columns:calc((100% - 2.25rem)/4)' in track
    assert 'grid-auto-columns:minmax(78vw,78vw)' in track
    assert 'overflow-x:auto' in track
    assert 'scroll-snap-type:x mandatory' in track
    assert track.count('class="novel-frame-card') == 4
    assert 'novel-frame-thought' in track
    assert 'border-style:dotted !important' in track
    assert 'font-style:italic' in track
    assert 'pensamento · Camilly' in track
    assert 'pensamento · Donisete' in track
    assert 'dialogue-user' in track
    assert 'dialogue-mary' in track


def test_paleta_fixa_segue_posicao_e_repete_a_cada_quatro_cards() -> None:
    sections = render_frame_sections(CONTENT, character_name="Camilly")

    assert sections is not None
    _description, track = sections
    assert ".novel-frame-card:nth-child(4n+1)" in track
    assert "--card-bg:#ED8BAE" in track
    assert ".novel-frame-card:nth-child(4n+2)" in track
    assert "--card-bg:#F1B5CB" in track
    assert ".novel-frame-card:nth-child(4n+3)" in track
    assert "--card-bg:#F0CFDD" in track
    assert ".novel-frame-card:nth-child(4n+4)" in track
    assert "--card-bg:#F3D5E6" in track
    assert "color:#2B1822 !important" in track


def test_caudas_acompanham_posicao_real_dos_cards() -> None:
    sections = render_frame_sections(CONTENT, character_name="Camilly")

    assert sections is not None
    _description, track = sections

    assert 'novel-frame-speech dialogue-message dialogue-mary tail-left' in track
    assert 'novel-frame-speech dialogue-message dialogue-user tail-center-left' in track
    assert 'novel-frame-thought tail-center-right' in track
    assert 'novel-frame-thought tail-right' in track

    assert ".novel-frame-card.tail-left{--tail-x:16%;}" in track
    assert ".novel-frame-card.tail-center-left{--tail-x:36%;}" in track
    assert ".novel-frame-card.tail-center-right{--tail-x:64%;}" in track
    assert ".novel-frame-card.tail-right{--tail-x:84%;}" in track


def test_fala_usa_ponta_e_pensamento_usa_bolinhas_para_cima() -> None:
    sections = render_frame_sections(CONTENT, character_name="Camilly")

    assert sections is not None
    _description, track = sections

    assert ".novel-frame-speech::before" in track
    assert "border-bottom:10px solid var(--card-bg)" in track
    assert "top:-9px" in track

    assert track.count('class="novel-thought-tail-dot"') == 2
    assert ".novel-frame-thought::before" in track
    assert ".novel-frame-thought::after" in track
    assert ".novel-frame-thought>.novel-thought-tail-dot" in track
    assert "top:-22px" in track


def test_renderizacao_de_compatibilidade_nao_contem_slot_de_imagem() -> None:
    rendered = render_frame_html(CONTENT, character_name="Camilly")

    assert rendered is not None
    assert "NOVEL_FRAME_IMAGE_SLOT" not in rendered
    assert rendered.count('<section class="novel-frame-v2">') == 1
    assert rendered.endswith("</section>")
