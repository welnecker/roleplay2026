from __future__ import annotations

from pathlib import Path

from packages.loader import load_manifest
from services.editorial_package_loader import compile_editorial_package
from services.editorial_runtime import EditorialState, decide_editorial_turn


CARD_ROOT = Path("installed_stories/casada_frustrada")


def _script():
    package = load_manifest(CARD_ROOT / "manifest.yaml")
    return compile_editorial_package(package)


def _state() -> EditorialState:
    return EditorialState(node_id="reencontro_fila_007")


def test_api_publica_do_app_executa_recusa_declarada() -> None:
    turn = decide_editorial_turn(
        _script(),
        _state(),
        "Não posso, estou atrasado.",
    )

    assert turn.target_id == "yard_help_refused_001"
    assert turn.state.node_id == "yard_help_refused_001"
    assert turn.state.facts["_last_user_intent"] == "refuse"
    assert turn.state.facts["help_to_car"] == "refused"


def test_api_publica_do_app_mantem_adiamento_no_beat() -> None:
    turn = decide_editorial_turn(
        _script(),
        _state(),
        "Agora não, talvez daqui a pouco.",
    )

    assert turn.target_id == "reencontro_fila_007"
    assert turn.state.node_id == "reencontro_fila_007"
    assert turn.state.facts["_last_user_intent"] == "postpone"
    assert "não avance" in turn.system_prompt.casefold()


def test_api_publica_do_app_mantem_pergunta_no_beat() -> None:
    turn = decide_editorial_turn(
        _script(),
        _state(),
        "Por que você precisa de ajuda?",
    )

    assert turn.target_id == "reencontro_fila_007"
    assert turn.state.node_id == "reencontro_fila_007"
    assert turn.state.facts["_last_user_intent"] == "question"
    assert "não presuma aceite" in turn.system_prompt.casefold()
