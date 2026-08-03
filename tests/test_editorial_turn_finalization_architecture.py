from __future__ import annotations

from pathlib import Path


IMPLEMENTATION = Path("services/editorial_progression_impl.py")
FINALIZATION = Path("services/editorial_turn_finalization.py")
SUPPORT = Path("services/editorial_progression_support.py")


def test_progressao_ativa_usa_finalizacao_especializada() -> None:
    source = IMPLEMENTATION.read_text(encoding="utf-8")

    assert "from services.editorial_turn_finalization import" in source
    assert "finalize_editorial_turn(" in source
    assert "editorial_progression_support" not in source


def test_modulo_monolitico_de_suporte_foi_removido() -> None:
    assert not SUPPORT.exists()
    source = FINALIZATION.read_text(encoding="utf-8")
    assert "def finalize_editorial_turn(" in source
    assert "build_narrative_context(" in source
    assert "_active_memory_ids" in source
    assert "strict_canonical" in source
