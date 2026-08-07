from __future__ import annotations

from services.editorial_content import load_source_document
from services.narrative_context import character_context


def test_mary_permanece_ousada_sem_romantizacao() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "intensamente hedonista e sexualmente frustrada" in context
    assert "não pretende divórcio, separação ou uma nova relação romântica" in context
    assert "não se apaixona pelo usuário" in context
    assert "viver uma aventura sexual secreta" in context
    assert "protege o segredo por estratégia e logística" in context


def test_motor_dominante_entra_no_prompt() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "motor dominante" in context
    assert "o desejo sexual é o motor dominante da personagem" in context
    assert "malícia, curiosidade física, provocação e imaginação" in context
    assert "o casamento não reduz o desejo" in context
    assert "não transforma desejo em romance" in context


def test_personalidade_nao_autoriza_antecipar_o_roteiro() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "não antecipar falas, convites, ações ou acontecimentos pertencentes a beats futuros" in context
    assert "o beat define o que acontece; o núcleo define como mary percebe" in context


def test_pensamento_preserva_a_voz_psicologica_do_nucleo() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "pensamento interno é curto, concreto, em primeira pessoa" in context
    assert "o primeiro filtro mental de mary diante de reciprocidade é desejo" in context
    assert "evitar culpa, autopiedade, fragilidade romântica, paixão" in context


def test_pontes_usam_o_mesmo_nucleo() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "improvisar a reação ao usuário a partir deste mesmo núcleo psicológico" in context
    assert "nunca como uma mary genérica ou romantizada" in context
