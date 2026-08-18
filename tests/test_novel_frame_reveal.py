from __future__ import annotations

from services.novel_frame_reveal import (
    frame_entry_count,
    frame_id,
    reveal_complete,
    reveal_frame_content,
)


CONTENT = """[QUADRO encontro_001]
[DESCRIÇÃO]
Camilly reconhece Janio no carro.
[FALA camilly|Camilly]
Oi, Janio!
[PENSAMENTO camilly|Camilly]
Que sorte encontrar ele agora.
[FALA usuario|Janio]
Oi, Camilly... chega mais.
[/QUADRO]"""


def test_descricao_aparece_antes_de_qualquer_entry() -> None:
    rendered = reveal_frame_content(CONTENT, 0)
    assert "Camilly reconhece Janio no carro." in rendered
    assert "Oi, Janio!" not in rendered
    assert "Que sorte encontrar ele agora." not in rendered
    assert "Oi, Camilly... chega mais." not in rendered


def test_cada_indice_revela_exatamente_a_proxima_entry() -> None:
    first = reveal_frame_content(CONTENT, 1)
    second = reveal_frame_content(CONTENT, 2)
    third = reveal_frame_content(CONTENT, 3)

    assert "Oi, Janio!" in first
    assert "Que sorte encontrar ele agora." not in first

    assert "Oi, Janio!" in second
    assert "Que sorte encontrar ele agora." in second
    assert "Oi, Camilly... chega mais." not in second

    assert "Oi, Camilly... chega mais." in third


def test_contagem_e_conclusao_do_quadro() -> None:
    assert frame_id(CONTENT) == "encontro_001"
    assert frame_entry_count(CONTENT) == 3
    assert reveal_complete(CONTENT, 2) is False
    assert reveal_complete(CONTENT, 3) is True
