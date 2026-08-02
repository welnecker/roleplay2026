from __future__ import annotations

from services.editorial_content import load_source_document
from services.narrative_context import character_context


def test_mary_permanece_ousada_mas_preserva_o_segredo() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "mulher casada e emocionalmente frustrada" in context
    assert "sente-se livre para flertar" in context
    assert "não convida interesses amorosos para sua residência" in context
    assert "prefere locais neutros, discretos ou previamente combinados" in context


def test_personalidade_nao_autoriza_antecipar_o_roteiro() -> None:
    document = load_source_document()
    context = character_context(document).casefold()

    assert "sem antecipar falas, convites ou acontecimentos de beats futuros" in context
