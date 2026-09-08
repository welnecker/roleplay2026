from __future__ import annotations

from services.editorial_content import load_source_document
from services.narrative_context import character_context


def test_mary_preserva_o_conflito_atual_sem_trocar_os_papeis() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "casada com o usuário" in context
    assert "ainda sente algo pelo marido" in context
    assert "professor da faculdade é um terceiro personagem distinto" in context
    assert "não transformar mary em hedonista genérica" in context
    assert "não transformar o usuário no amante de mary" in context


def test_motor_dominante_entra_no_prompt() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "motor dominante" in context
    assert "mary busca carinho, amor, paixão e sexo" in context
    assert "desejo é intenso, corporal e consciente" in context
    assert "o usuário é o marido de mary" in context
    assert "a suspeita de que o marido possa ser gay é uma hipótese" in context


def test_personalidade_nao_autoriza_antecipar_o_roteiro() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "não antecipar falas, convites, ações ou acontecimentos pertencentes a beats futuros" in context
    assert "o beat define o que acontece; o núcleo define como mary sente" in context


def test_pensamento_preserva_a_voz_psicologica_do_nucleo() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "pensamento interno é curto, concreto, em primeira pessoa" in context
    assert "ligado ao desejo, ao conflito conjugal ou à situação imediata" in context
    assert "preservar a ambivalência" in context
    assert "nunca diagnóstico ou certeza" in context


def test_pontes_usam_o_mesmo_nucleo() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "improvisar somente dentro do movimento atual" in context
    assert "manter clara a diferença entre marido e professor" in context
    assert "a ponte pode aprofundar emoção e desejo" in context
