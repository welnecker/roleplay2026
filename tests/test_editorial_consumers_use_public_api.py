from __future__ import annotations

from pathlib import Path

from services.editorial_progression import (
    clean_editorial_progression_response,
    prepare_editorial_script,
)
from services.editorial_runtime import EditorialScript, EditorialState, EditorialTurn


def test_carregador_de_pacote_usa_api_editorial_publica() -> None:
    source = Path("services/editorial_package_loader.py").read_text(encoding="utf-8")

    assert "from services.editorial_runtime import EditorialScript" in source
    assert "from services.editorial_progression import prepare_editorial_script" in source
    assert "from services.pilot_supermarket import PilotScript" not in source
    assert "prepare_supermarket_script_v2" not in source


def test_servico_de_conteudo_expoe_tipo_editorial() -> None:
    source = Path("services/editorial_content.py").read_text(encoding="utf-8")

    assert "from services.editorial_runtime import EditorialScript" in source
    assert ") -> EditorialScript:" in source
    assert "from services.pilot_supermarket import PilotScript" not in source
    assert "from services.supermarket_script_v2 import" not in source


def test_api_editorial_preserva_contratos_compativeis() -> None:
    assert EditorialScript.__name__ == "PilotScript"
    assert EditorialState.__name__ == "PilotState"
    assert EditorialTurn.__name__ == "PilotTurn"
    assert callable(prepare_editorial_script)
    assert callable(clean_editorial_progression_response)
