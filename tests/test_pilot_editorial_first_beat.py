from services.pilot_supermarket import PilotScript, PilotState, decide_turn, opening_text


def _script() -> PilotScript:
    return PilotScript(
        {
            "engagement_policy": {"categories": {}},
            "scene": {
                "first_beat_id": "encontro_acidental_001",
                "beats": [
                    {
                        "beat_id": "encontro_acidental_001",
                        "objective": "Mary pede desculpas.",
                        "units": [
                            {
                                "unit_id": "opening",
                                "kind": "dialogue",
                                "delivery": "anchored",
                                "anchor": "Eita, caralho... desculpa!",
                            },
                            {"unit_id": "wait", "kind": "wait_user"},
                        ],
                        "on_user": {
                            "engaged": "encontro_acidental_002",
                            "minimal": "encontro_acidental_002",
                        },
                    },
                    {
                        "beat_id": "encontro_acidental_002",
                        "objective": "Mary confirma se está tudo bem.",
                        "units": [
                            {
                                "unit_id": "check",
                                "kind": "dialogue",
                                "delivery": "anchored",
                                "anchor": "Tem certeza que tá tudo bem?",
                            },
                            {"unit_id": "wait2", "kind": "wait_user"},
                        ],
                        "on_user": {"engaged": "end_hostile"},
                    },
                ],
                "endings": [
                    {
                        "ending_id": "end_hostile",
                        "run_status": "terminated",
                        "ending_code": "hostile",
                        "visible_delivery": {"text": "Chega."},
                    }
                ],
            },
        }
    )


def test_abertura_usa_primeiro_beat_editorial() -> None:
    script = _script()
    assert script.first_beat_id == "encontro_acidental_001"
    assert opening_text(script) == "Eita, caralho... desculpa!"


def test_estado_antigo_collision_migra_para_primeiro_beat() -> None:
    script = _script()
    turn = decide_turn(script, PilotState(node_id="collision"), "Estou bem, não se preocupe.")
    assert turn.target_id == "encontro_acidental_002"
    assert turn.state.node_id == "encontro_acidental_002"
    assert turn.visible_fallback == "Tem certeza que tá tudo bem?"
