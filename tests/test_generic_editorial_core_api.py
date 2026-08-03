from __future__ import annotations

from pathlib import Path

from services.editorial_diagnostics import (
    EditorialGuardedResponse,
    build_editorial_turn_diagnostics,
    finalize_editorial_model_response,
)
from services.editorial_progression import (
    decide_editorial_progression_turn,
    prepare_editorial_script,
    decide_supermarket_script_v2_turn,
    prepare_supermarket_script_v2,
)
from services.editorial_runtime import (
    EditorialScript,
    EditorialState,
    EditorialTurn,
    clean_editorial_model_response,
    decide_editorial_turn,
)
from services.editorial_runtime_impl import PilotScript, PilotState, PilotTurn
from services.pilot_diagnostics import GuardedResponse


def test_tipos_editoriais_preservam_compatibilidade() -> None:
    assert EditorialScript is PilotScript
    assert EditorialState is PilotState
    assert EditorialTurn is PilotTurn
    assert EditorialGuardedResponse is GuardedResponse


def test_progressao_editorial_preserva_implementacao_atual() -> None:
    assert prepare_editorial_script is prepare_supermarket_script_v2
    assert decide_editorial_progression_turn is decide_supermarket_script_v2_turn


def test_api_editorial_expoe_operacoes_principais() -> None:
    assert callable(decide_editorial_turn)
    assert callable(clean_editorial_model_response)
    assert callable(build_editorial_turn_diagnostics)
    assert callable(finalize_editorial_model_response)


def test_modulos_publicos_nao_conhecem_historia_especifica() -> None:
    for path in (
        Path("services/editorial_runtime.py"),
        Path("services/editorial_progression.py"),
        Path("services/editorial_diagnostics.py"),
    ):
        source = path.read_text(encoding="utf-8").casefold()
        assert "casada_frustrada" not in source
        assert "roleplay2026." not in source
        assert "mary" not in source
        assert "motel" not in source


def test_novos_consumidores_devem_usar_api_editorial() -> None:
    source = Path("services/editorial_runtime.py").read_text(encoding="utf-8")
    assert "__all__" in source
    assert "EditorialState" in source
    assert "EditorialScript" in source
