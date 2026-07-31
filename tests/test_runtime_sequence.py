from __future__ import annotations

from services.runtime_persistence import _next_sequence_from_messages


def test_nova_sessao_continua_maior_sequencia_da_run() -> None:
    messages = [
        {"sequence": 21, "role": "user"},
        {"sequence": 22, "role": "assistant"},
        {"sequence": 35, "role": "user"},
        {"sequence": 36, "role": "assistant"},
    ]

    assert _next_sequence_from_messages(messages) == 37


def test_nova_run_comeca_em_um() -> None:
    assert _next_sequence_from_messages([]) == 1


def test_duplicidades_antigas_nao_reiniciam_sequencia() -> None:
    messages = [
        {"sequence": 21},
        {"sequence": 22},
        {"sequence": 36},
        {"sequence": 21},
        {"sequence": 22},
    ]

    assert _next_sequence_from_messages(messages) == 37
