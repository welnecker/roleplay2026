from __future__ import annotations

from types import SimpleNamespace

from roleplay.models import StoryState
from services import runtime_persistence
from services.runtime_persistence import (
    RuntimePersistenceContext,
    _next_sequence_from_messages,
    persist_opening_message,
)


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


def test_abertura_e_persistida_com_personagem_e_sem_usuario_ficticio(monkeypatch) -> None:
    run = SimpleNamespace(
        run_id="run_1",
        current_block_id="abertura",
        current_beat_id="abertura_001",
    )
    session = SimpleNamespace(session_id="sess_1")

    class Repository:
        def __init__(self) -> None:
            self.appended = []

        def append_interaction(self, **kwargs):
            self.appended.append(kwargs)

        def update_run_progress(self, **kwargs):
            return kwargs["run"]

    repository = Repository()
    monkeypatch.setattr(
        runtime_persistence,
        "_ensure_run_and_session",
        lambda *args, **kwargs: (run, session),
    )
    context = RuntimePersistenceContext(
        package_id="roleplay2026.camilly",
        package_version="1.1.2001",
        run=run,
        session=session,
        next_sequence=1,
    )

    updated = persist_opening_message(
        repository,
        context=context,
        user=SimpleNamespace(user_id="user_1"),
        state=StoryState(),
        assistant_text="Oi, Vini... gostei de ver você aqui.",
        assistant_metadata={
            "editorial_node": "abertura_001",
            "character_id": "camilly",
        },
    )

    assert len(repository.appended) == 1
    assert repository.appended[0]["role"] == "assistant"
    assert repository.appended[0]["speaker_id"] == "camilly"
    assert repository.appended[0]["sequence"] == 1
    assert repository.appended[0]["beat_id"] == "abertura_001"
    assert repository.appended[0]["metadata"]["opening_message"] is True
    assert updated.next_sequence == 2
