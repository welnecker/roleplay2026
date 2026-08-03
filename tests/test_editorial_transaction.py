from __future__ import annotations

from pathlib import Path

import pytest

from packages.loader import load_manifest
from services.editorial_package_loader import compile_editorial_package
from services.editorial_runtime import EditorialState, decide_editorial_turn
from services.editorial_transaction import (
    commit_editorial_turn,
    prepare_pending_editorial_turn,
)


FIXTURE_ROOT = Path("tests/fixtures/editorial_cards/encontro_no_cafe")


def _script():
    return compile_editorial_package(load_manifest(FIXTURE_ROOT / "manifest.yaml"))


def test_pending_turn_preserva_estado_anterior_e_propoe_novo_estado() -> None:
    script = _script()
    previous = EditorialState()
    turn = decide_editorial_turn(script, previous, "Olá, prazer em conhecer você.")

    pending = prepare_pending_editorial_turn(script, previous, turn)

    assert pending.previous_state.to_dict() == previous.to_dict()
    assert pending.proposed_state.to_dict() == turn.state.to_dict()
    assert pending.previous_state is not previous
    assert pending.proposed_state is not turn.state
    assert pending.context.target_beat_id == turn.target_id


def test_commit_exige_resposta_aprovada_nao_vazia() -> None:
    script = _script()
    previous = EditorialState()
    turn = decide_editorial_turn(script, previous, "Olá, prazer em conhecer você.")
    pending = prepare_pending_editorial_turn(script, previous, turn)

    with pytest.raises(ValueError):
        commit_editorial_turn(pending, "   ")


def test_commit_materializa_copia_do_estado_proposto() -> None:
    script = _script()
    previous = EditorialState()
    turn = decide_editorial_turn(script, previous, "Olá, prazer em conhecer você.")
    pending = prepare_pending_editorial_turn(script, previous, turn)

    committed = commit_editorial_turn(pending, "Uma resposta aprovada.")

    assert committed.response == "Uma resposta aprovada."
    assert committed.state.to_dict() == pending.proposed_state.to_dict()
    assert committed.state is not pending.proposed_state
    assert previous.to_dict() == pending.previous_state.to_dict()
