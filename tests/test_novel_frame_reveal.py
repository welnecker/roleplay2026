from __future__ import annotations

from services.novel_frame_reveal import (
    frame_entry_count,
    frame_id,
    normalize_frame_markers,
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

INLINE_CONTENT = """[QUADRO encontro_001]
[DESCRIÇÃO]
Janio reduz a velocidade ao avistar Camilly caminhando sob o sol.
[FALA camilly|Camilly] Oi! Não acredito que te encontrei por aqui!
[FALA usuario|Janio] Que coincidência, Camilly! Vem cá.
[PENSAMENTO camilly|Camilly] Que sorte encontrar ele justamente agora...
[PENSAMENTO usuario|Janio] Ela parece bem contente em me encontrar.
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


def test_tag_sem_conteudo_nao_cria_clique_sem_balao() -> None:
    content = """[QUADRO encontro_002]
[DESCRIÇÃO]
Camilly se aproxima do carro.
[FALA camilly|Camilly]
Oi!
[PENSAMENTO usuario|Janio]
[FALA usuario|Janio]
Entra aí.
[/QUADRO]"""

    assert frame_entry_count(content) == 2
    complete = reveal_frame_content(content, 2)
    assert "Oi!" in complete
    assert "Entra aí." in complete
    assert "[PENSAMENTO" not in complete


def test_tags_inline_sao_normalizadas_e_contadas_separadamente() -> None:
    normalized = normalize_frame_markers(INLINE_CONTENT)

    assert "[FALA camilly|Camilly]\nOi! Não acredito" in normalized
    assert "[PENSAMENTO usuario|Janio]\nEla parece" in normalized
    assert frame_id(INLINE_CONTENT) == "encontro_001"
    assert frame_entry_count(INLINE_CONTENT) == 4


def test_revelacao_inline_nao_vaza_falas_para_descricao() -> None:
    opening = reveal_frame_content(INLINE_CONTENT, 0)
    complete = reveal_frame_content(INLINE_CONTENT, 4)

    assert "Janio reduz a velocidade" in opening
    assert "[FALA" not in opening
    assert "Oi! Não acredito" not in opening
    assert "Oi! Não acredito" in complete
    assert "Que coincidência, Camilly!" in complete
    assert "Que sorte encontrar ele" in complete
    assert "Ela parece bem contente" in complete
