from __future__ import annotations

from services import editorial_runtime
from services import editorial_turn_engine as engine
from services.editorial_contextual_destination import ContextualDestination
from services.editorial_player_contextual_cycle import install_contextual_player_cycle
from services.editorial_runtime_impl import PilotScript, PilotState, PilotTurn


def _script(package_id: str = "example.chapter") -> PilotScript:
    return PilotScript(
        {
            "package_id": package_id,
            "character": {"name": "Mary"},
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "beat_001",
                "terminal_yards": {},
                "beats": [
                    {
                        "beat_id": "beat_001",
                        "block_id": "opening",
                        "units": [],
                        "on_user": {"engaged": "beat_002"},
                    },
                    {
                        "beat_id": "beat_002",
                        "block_id": "opening",
                        "units": [],
                        "on_user": {},
                    },
                ],
                "endings": [],
            },
        }
    )


def test_motor_classifica_ponte_antes_da_progressao(monkeypatch) -> None:
    script = _script()
    previous = PilotState(node_id="beat_001")
    observed: list[str] = []

    def classify(received_script, received_state, user_text, *, classifier_call):
        observed.append("bridge")
        assert received_script is script
        assert user_text == "Continuo aqui."
        assert classifier_call("prompt", "request") == "classified"
        updated = PilotState.from_dict(received_state.to_dict())
        updated.facts["_contextual_route"] = "continue"
        return updated, ContextualDestination(
            route="continue",
            signal="compatible_response",
            confidence=0.95,
        )

    def progress(received_script, received_state, user_text):
        observed.append("beat")
        assert received_script is script
        assert received_state.facts["_contextual_route"] == "continue"
        return PilotTurn(
            engagement="engaged",
            target_id="beat_002",
            visible_fallback="Próximo movimento.",
            system_prompt="beat",
            state=received_state,
        )

    monkeypatch.setattr(engine, "classify_contextual_destination_for_turn", classify)
    monkeypatch.setattr(engine, "decide_editorial_progression_turn", progress)

    turn = engine.decide_editorial_turn(
        script,
        previous,
        "Continuo aqui.",
        classifier_call=lambda _prompt, _request: "classified",
    )

    assert observed == ["bridge", "beat"]
    assert turn.target_id == "beat_002"


def test_player_registra_classificador_sem_substituir_runtime() -> None:
    public_decide_before = editorial_runtime.decide_editorial_turn

    install_contextual_player_cycle()

    assert editorial_runtime.decide_editorial_turn is public_decide_before
    assert editorial_runtime.decide_editorial_turn is engine.decide_editorial_turn


def test_motor_nao_compartilha_estado_entre_cards(monkeypatch) -> None:
    seen_packages: list[str] = []

    def classify(received_script, received_state, user_text, *, classifier_call):
        seen_packages.append(str(received_script.raw["package_id"]))
        updated = PilotState.from_dict(received_state.to_dict())
        updated.facts["chapter_marker"] = str(received_script.raw["package_id"])
        return updated, ContextualDestination(route="continue")

    def progress(received_script, received_state, user_text):
        return PilotTurn(
            engagement="engaged",
            target_id="beat_002",
            visible_fallback="continua",
            system_prompt="beat",
            state=received_state,
        )

    monkeypatch.setattr(engine, "classify_contextual_destination_for_turn", classify)
    monkeypatch.setattr(engine, "decide_editorial_progression_turn", progress)

    first = engine.decide_editorial_turn(_script("chapter.one"), PilotState(node_id="beat_001"), "A")
    second = engine.decide_editorial_turn(_script("chapter.two"), PilotState(node_id="beat_001"), "B")

    assert seen_packages == ["chapter.one", "chapter.two"]
    assert first.state.facts["chapter_marker"] == "chapter.one"
    assert second.state.facts["chapter_marker"] == "chapter.two"
