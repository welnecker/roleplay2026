from __future__ import annotations

from services.novel_frame_presentation import render_frame_html


def test_descricao_tem_card_proprio_e_pensamento_tem_borda_pontilhada_italico() -> None:
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
    assert 'class="novel-frame-thought"' in rendered
    assert 'border:2px dotted' in rendered
    assert 'font-style:italic' in rendered
    assert 'pensamento · Camilly' in rendered
    assert 'pensamento · Donisete' in rendered
    assert 'dialogue-message dialogue-mary' in rendered
    assert 'dialogue-message dialogue-user' in rendered
