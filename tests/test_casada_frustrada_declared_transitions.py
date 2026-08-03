from __future__ import annotations

from pathlib import Path

from packages.loader import discover_packages
from services.editorial_package_loader import compile_editorial_package, load_editorial_document
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime import EditorialState


ROOT = Path("installed_stories")
PACKAGE_ID = "roleplay2026.casada_frustrada"
BEAT_ID = "reencontro_fila_007"


def _package():
    packages, errors = discover_packages(ROOT)
    assert errors == []
    return next(item for item in packages if item.manifest.package_id == PACKAGE_ID)


def _script():
    return compile_editorial_package(_package())


def _state() -> EditorialState:
    return EditorialState(node_id=BEAT_ID)


def test_pedido_de_ajuda_usa_transicoes_do_proprio_beat() -> None:
    script = _script()
    beat = script.beats[BEAT_ID]

    assert beat["intent_classifiers"]
    assert {rule.transition_id for rule in beat["transition_rules"]} == {
        "help_accepted",
        "help_refused",
        "help_question",
        "help_postponed",
        "help_unclear",
    }


def test_aceite_avanca_para_caminho_ao_carro() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        _state(),
        "Claro, eu espero e ajudo você.",
    )

    assert turn.target_id == "reencontro_fila_008"
    assert turn.state.facts["help_to_car"] == "accepted"
    assert turn.state.facts["_last_user_intent"] == "accept"


def test_recusa_entra_no_patio_de_recusa() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        _state(),
        "Não posso esperar, estou atrasado.",
    )

    assert turn.target_id == "yard_help_refused_001"
    assert turn.state.facts["help_to_car"] == "refused"
    assert turn.state.facts["_last_user_intent"] == "refuse"


def test_pergunta_permanece_no_beat_sem_presumir_aceite() -> None:
    turn = decide_editorial_progression_turn(
        _script(),
        _state(),
        "Por que você precisa de ajuda?",
    )

    assert turn.target_id == BEAT_ID
    assert turn.state.facts["_last_user_intent"] == "question"
    assert "help_to_car" not in turn.state.facts
    assert "não avance" in turn.system_prompt.casefold()


def test_decisao_especial_antiga_foi_removida_do_card() -> None:
    document = load_editorial_document(_package())
    organic = document.get("organic_slack") or {}
    decisions = organic.get("special_decisions") or []

    assert all(str(item.get("beat_id", "")) != BEAT_ID for item in decisions)
