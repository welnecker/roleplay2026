from __future__ import annotations

from services.editorial_bridge import should_create_bridge
from services.editorial_routing import routing_state_for_declared_skips
from services.editorial_runtime import EditorialScript, EditorialState, EditorialTurn


def _script() -> EditorialScript:
    return EditorialScript(
        {
            "bridge_policy": {"mode": "required"},
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "beat_1",
                "beats": [
                    {
                        "beat_id": "beat_1",
                        "block_id": "main",
                        "units": [{"kind": "dialogue", "anchor": "Um"}],
                        "on_user": {"engaged": "beat_2"},
                    },
                    {
                        "beat_id": "beat_2",
                        "block_id": "main",
                        "units": [{"kind": "dialogue", "anchor": "Dois"}],
                        "on_user": {"engaged": "beat_3"},
                    },
                    {
                        "beat_id": "beat_3",
                        "block_id": "main",
                        "units": [{"kind": "dialogue", "anchor": "Três"}],
                        "skip_when_facts": {"known": "beat_4"},
                        "on_user": {"engaged": "beat_4"},
                    },
                    {
                        "beat_id": "beat_4",
                        "block_id": "main",
                        "units": [{"kind": "dialogue", "anchor": "Quatro"}],
                        "on_user": {"engaged": "beat_4"},
                    },
                ],
                "endings": [],
            },
        }
    )


def _turn(target_id: str, facts: dict[str, str]) -> EditorialTurn:
    return EditorialTurn(
        engagement="engaged",
        target_id=target_id,
        visible_fallback="",
        system_prompt="",
        state=EditorialState(node_id=target_id, facts=facts),
    )


def test_decisao_explicita_do_beat_atual_evitar_ponte_redundante() -> None:
    script = _script()
    previous = EditorialState(node_id="beat_1")
    turn = _turn(
        "beat_2",
        {
            "_last_user_explicit_decision": "true",
            "_last_user_intent_beat_id": "beat_1",
        },
    )

    assert should_create_bridge(script, previous, turn) is False


def test_decisao_explicita_antiga_nao_desativa_ponte_futura() -> None:
    script = _script()
    previous = EditorialState(node_id="beat_2")
    turn = _turn(
        "beat_3",
        {
            "_last_user_explicit_decision": "true",
            "_last_user_intent_beat_id": "beat_1",
        },
    )

    assert should_create_bridge(script, previous, turn) is True


def test_salto_declarado_registra_o_beat_que_o_aplicou() -> None:
    script = _script()
    state = EditorialState(node_id="beat_2", facts={"known": "yes"})

    routed = routing_state_for_declared_skips(
        script,
        state,
        "engaged",
        original_facts={"known": "yes"},
    )

    assert routed.pending_next_beat_id == "beat_4"
    assert routed.facts["_declared_skip_applied"] == "beat_3"
    assert routed.facts["_declared_skip_origin_beat_id"] == "beat_2"


def test_salto_declarado_antigo_nao_desativa_ponte_futura() -> None:
    script = _script()
    previous = EditorialState(node_id="beat_2")
    turn = _turn(
        "beat_3",
        {
            "_declared_skip_applied": "beat_1",
            "_declared_skip_origin_beat_id": "beat_1",
        },
    )

    assert should_create_bridge(script, previous, turn) is True
