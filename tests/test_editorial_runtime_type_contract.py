from __future__ import annotations

from pathlib import Path

from services.editorial_runtime import (
    EditorialScript,
    EditorialState,
    EditorialTurn,
)
from services.editorial_runtime_types import (
    EditorialScript as ContractScript,
    EditorialState as ContractState,
    EditorialTurn as ContractTurn,
)


PUBLIC_RUNTIME = Path("services/editorial_runtime.py")
PROGRESSION = Path("services/editorial_progression_impl.py")
TYPE_CONTRACT = Path("services/editorial_runtime_types.py")


def test_api_publica_usa_contrato_central_de_tipos() -> None:
    assert EditorialScript is ContractScript
    assert EditorialState is ContractState
    assert EditorialTurn is ContractTurn

    source = PUBLIC_RUNTIME.read_text(encoding="utf-8")
    assert "from services.editorial_runtime_types import" in source
    assert "PilotScript" not in source
    assert "PilotState" not in source
    assert "PilotTurn" not in source


def test_progressao_ativa_usa_nomes_editoriais() -> None:
    source = PROGRESSION.read_text(encoding="utf-8")

    assert "from services.editorial_runtime_types import" in source
    assert "EditorialScript" in source
    assert "EditorialState" in source
    assert "EditorialTurn" in source
    assert "PilotScript" not in source
    assert "PilotState" not in source
    assert "PilotTurn" not in source


def test_compatibilidade_pilot_fica_isolada_no_contrato_temporario() -> None:
    source = TYPE_CONTRACT.read_text(encoding="utf-8")

    assert "PilotScript as EditorialScript" in source
    assert "PilotState as EditorialState" in source
    assert "PilotTurn as EditorialTurn" in source
