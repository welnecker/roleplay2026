from __future__ import annotations

from services.novel_frame_presentation import render_frame_sections


INLINE_OUTPUT = """[QUADRO encontro_001]
[DESCRIÇÃO]
Janio reduz a velocidade ao avistar Camilly caminhando sob o sol, radiante em seu biquíni, e encosta o carro próximo ao meio-fio.
[FALA camilly|Camilly] Oi! Não acredito que te encontrei por aqui, estava mesmo indo para o ponto!
[FALA usuario|Janio] Que coincidência, Camilly! Vem cá, encosta aqui no carro.
[PENSAMENTO camilly|Camilly] Que sorte encontrar ele justamente agora... talvez esse dia fique mais interessante do que eu estava imaginando.
[PENSAMENTO usuario|Janio] Ela parece bem contente em me encontrar. Vou ver o que ela quer.
[/QUADRO]"""


def test_saida_inline_nao_mistura_falas_com_cena() -> None:
    sections = render_frame_sections(INLINE_OUTPUT, character_name="Camilly")

    assert sections is not None
    description, track = sections

    assert "Janio reduz a velocidade" in description
    assert "Oi! Não acredito" not in description
    assert "[FALA" not in description
    assert "[PENSAMENTO" not in description

    assert track.count('class="novel-frame-card') == 4
    assert "Oi! Não acredito" in track
    assert "Que coincidência, Camilly!" in track
    assert "Que sorte encontrar ele justamente agora" in track
    assert "Ela parece bem contente em me encontrar" in track
    assert "[FALA" not in track
    assert "[PENSAMENTO" not in track
