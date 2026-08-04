from __future__ import annotations

import json

from services import editorial_player_contextual_cycle as cycle
from services.editorial_bridge import bridge_enabled_for_beat, bridge_policy
from services.editorial_runtime_impl import PilotScript, PilotState, PilotTurn


def _script(*, with_policy: bool = True) -> PilotScript:
    raw = {
        "package_id": "example.generic_card",
        "character": {"name": "Mary"},
        "engagement_policy": {"categories": {}},
        "scene": {
            "first_beat_id": "encontro_001",
            "terminal_yards": {},
            "beats": [
                {
                    "beat_id": "encontro_001",
                    "block_id": "encontro_acidental",
                    "units": [],
                    "on_user": {"engaged": "encontro_002"},
                    "interaction_context": {
                        "relationship_stage": "strangers",
                        "setting": "supermarket",
                        "privacy": "public",
                        "intimacy_level": 0,
                        "allowed_interactions": ["light_flirting"],
                    },
                },
                {
                    "beat_id": "encontro_002",
                    "block_id": "encontro_acidental",
                    "units": [],
                    "on_user": {},
                },
                {
                    "beat_id": "motel_001",
                    "block_id": "motel",
                    "units": [],
                    "on_user": {},
                },
            ],
            "endings": [],
        },
    }
    if with_policy:
        raw["organic_slack"] = {
            "bridge_policy": {
                "mode": "required",
                "block_ids": ["encontro_acidental", "reencontro_fila"],
                "exclude_block_ids": ["motel"],
            }
        }
    return PilotScript(raw)


def test_politica_declarada_ativa_somente_blocos_selecionados() -> None:
    script = _script()

    assert bridge_policy(script)["mode"] == "required"
    assert bridge_enabled_for_beat(script, "encontro_001") is True
    assert bridge_enabled_for_beat(script, "motel_001") is False


def test_card_sem_politica_permanece_no_comportamento_legado() -> None:
    script = _script(with_policy=False)

    assert bridge_policy(script) == {}
    assert bridge_enabled_for_beat(script, "encontro_001") is False


def test_politica_top_level_tem_precedencia_sobre_conteiner_historico() -> None:
    script = _script()
    script.raw["bridge_policy"] = {"mode": "disabled"}

    assert bridge_policy(script) == {"mode": "disabled"}
    assert bridge_enabled_for_beat(script, "encontro_001") is False


def test_player_classifica_antes_de_chamar_roteador(monkeypatch) -> None:
    script = _script()
    previous = PilotState(node_id="encontro_001")
    observed: dict[str, str] = {}

    monkeypatch.setattr(
        cycle,
        "_classifier_call",
        lambda prompt, request: json.dumps(
            {
                "route": "continue",
                "signal": "light_flirting",
                "reason": "compatível com o contexto",
                "confidence": 0.94,
            }
        ),
    )

    def decide(received_script, received_state, user_text):
        observed["route"] = received_state.facts.get("_contextual_route", "")
        observed["signal"] = received_state.facts.get("_contextual_signal", "")
        state = PilotState.from_dict(received_state.to_dict())
        state.node_id = "encontro_002"
        return PilotTurn(
            engagement="engaged",
            target_id="encontro_002",
            visible_fallback="Tudo bem.",
            system_prompt="continue",
            state=state,
        )

    monkeypatch.setattr(cycle, "_ORIGINAL_DECIDE", decide)
    turn = cycle.decide_player_editorial_turn(
        script,
        previous,
        "Você é bonita.",
    )

    assert observed == {"route": "continue", "signal": "light_flirting"}
    assert turn.state.facts["_contextual_route"] == "continue"
    assert turn.state.facts["_contextual_confidence"] == "0.940"
