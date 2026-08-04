import json

from services.editorial_contextual_orchestration import (
    classify_contextual_destination_for_turn,
)
from services.editorial_runtime_impl import PilotScript, PilotState


def _script(*, contextual: bool = True) -> PilotScript:
    interaction_context = (
        {
            "relationship_stage": "strangers",
            "setting": "public",
            "privacy": "public",
            "intimacy_level": 0,
            "allowed_interactions": ["light_flirting"],
            "terminal_violations": ["explicit_sexual_proposition_before_mutual_intimacy"],
            "terminal_yard_target": "yard_001",
        }
        if contextual
        else {}
    )
    return PilotScript(
        {
            "character": {"name": "Lia"},
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "beat_001",
                "terminal_yards": {
                    "yard": {
                        "entry_beat_id": "yard_001",
                        "beat_ids": ["yard_001"],
                        "ending_ids": [],
                    }
                },
                "beats": [
                    {
                        "beat_id": "beat_001",
                        "units": [],
                        "on_user": {"engaged": "beat_002"},
                        "interaction_context": interaction_context,
                    },
                    {"beat_id": "beat_002", "units": [], "on_user": {}},
                    {
                        "beat_id": "yard_001",
                        "units": [],
                        "on_user": {},
                        "terminal_yard_id": "yard",
                    },
                ],
                "endings": [],
            },
        }
    )


def test_classificador_e_chamado_uma_unica_vez_sem_receber_destinos() -> None:
    calls: list[tuple[str, str]] = []

    def classify(prompt: str, request: str) -> str:
        calls.append((prompt, request))
        return json.dumps(
            {
                "route": "terminal_yard",
                "signal": "explicit_sexual_proposition_before_mutual_intimacy",
                "reason": "ruptura no primeiro contato",
                "confidence": 0.98,
            }
        )

    updated, destination = classify_contextual_destination_for_turn(
        _script(),
        PilotState(node_id="beat_001"),
        "Quero transar com você agora.",
        classifier_call=classify,
    )

    assert len(calls) == 1
    prompt, request = calls[0]
    assert "yard_001" not in prompt
    assert "yard_001" not in request
    assert destination.route == "terminal_yard"
    assert updated.facts["_contextual_route"] == "terminal_yard"
    assert updated.facts["_contextual_signal"] == destination.signal


def test_contexto_sem_sinais_nao_consume_chamada_de_modelo() -> None:
    called = False

    def classify(prompt: str, request: str) -> str:
        nonlocal called
        called = True
        return "{}"

    updated, destination = classify_contextual_destination_for_turn(
        _script(contextual=False),
        PilotState(node_id="beat_001"),
        "Olá.",
        classifier_call=classify,
    )

    assert called is False
    assert destination.route == "continue"
    assert updated.facts["_contextual_route"] == "continue"


def test_saida_invalida_preserva_continuidade() -> None:
    updated, destination = classify_contextual_destination_for_turn(
        _script(),
        PilotState(node_id="beat_001"),
        "Você é bonita.",
        classifier_call=lambda prompt, request: "não é json",
    )

    assert destination.route == "continue"
    assert destination.reason == "invalid_classifier_output"
    assert updated.facts["_contextual_route"] == "continue"
