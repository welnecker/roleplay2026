from __future__ import annotations

from pathlib import Path


SPECIALIZED_MODULES = (
    Path("services/editorial_routing.py"),
    Path("services/editorial_followups.py"),
    Path("services/editorial_organic_turns.py"),
    Path("services/editorial_declared_decisions.py"),
)


def test_modulos_especializados_usam_contrato_de_tipos_editoriais() -> None:
    for path in SPECIALIZED_MODULES:
        source = path.read_text(encoding="utf-8")
        assert "from services.editorial_runtime_types import" in source
        assert "from services.editorial_runtime_impl import Pilot" not in source


def test_modulos_especializados_nao_mencionam_tipos_pilot() -> None:
    forbidden = ("PilotScript", "PilotState", "PilotTurn")
    for path in SPECIALIZED_MODULES:
        source = path.read_text(encoding="utf-8")
        for name in forbidden:
            assert name not in source


def test_contrato_editorial_cobre_assinaturas_dos_modulos() -> None:
    routing = SPECIALIZED_MODULES[0].read_text(encoding="utf-8")
    followups = SPECIALIZED_MODULES[1].read_text(encoding="utf-8")
    organic = SPECIALIZED_MODULES[2].read_text(encoding="utf-8")
    decisions = SPECIALIZED_MODULES[3].read_text(encoding="utf-8")

    assert "script: EditorialScript" in routing
    assert "state: EditorialState" in routing
    assert "ContextVar[EditorialScript | None]" in followups
    assert ") -> EditorialTurn | None:" in organic
    assert "DecisionFunction = Callable[[EditorialScript, EditorialState, str], EditorialTurn]" in decisions
