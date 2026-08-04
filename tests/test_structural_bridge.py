from services.editorial_bridge import bridge_active, bridge_target_id
from services.editorial_progression_impl import decide_editorial_progression_turn
from services.editorial_runtime_impl import PilotScript, PilotState


def _beat(beat_id: str, line: str, target: str) -> dict[str, object]:
    return {
        "beat_id": beat_id,
        "objective": f"movimento de {beat_id}",
        "units": [
            {
                "unit_id": f"{beat_id}_dialogue",
                "kind": "dialogue",
                "delivery": "anchored",
                "anchor": line,
                "instruction": f"direção de {beat_id}",
            },
            {"unit_id": f"{beat_id}_wait", "kind": "wait_user"},
        ],
        "on_user": {
            "engaged": target,
            "minimal": target,
            "dismissive": target,
            "nonsense": target,
        },
        "transition_rules": (),
        "intent_classifiers": [],
        "terminal_transition": "",
        "memory_writes": [],
        "max_questions": 1,
        "max_sentences": 3,
        "skip_when_facts": {},
        "response_boundary": "",
        "allowed_topics": [],
        "confirmed_facts": [],
        "unknown_facts": [],
        "constraints": {},
        "block_id": "main",
        "block_type": "canonical",
        "position_in_block": 1,
        "block_size": 3,
        "terminal_yard_id": "",
        "yard_min_user_turns": 0,
        "yard_max_user_turns": 0,
        "interaction_context": {},
    }


def _script() -> PilotScript:
    raw = {
        "character": {"name": "Lia"},
        "engagement_policy": {"categories": {}},
        "scene": {
            "scene_id": "main",
            "location": "cafeteria",
            "objective": "aproximação",
            "first_beat_id": "beat_001",
            "terminal_yards": {},
            "beats": [
                _beat("beat_001", "Oi.", "beat_002"),
                _beat("beat_002", "Você vem sempre aqui?", "beat_003"),
                _beat("beat_003", "Posso sentar?", "beat_003"),
            ],
            "endings": [],
        },
    }
    return PilotScript(raw)


def test_primeira_resposta_cria_uma_ponte_sem_avancar_o_beat() -> None:
    script = _script()
    state = PilotState()

    turn = decide_editorial_progression_turn(
        script,
        state,
        "Gostei do seu sorriso.",
    )

    assert turn.target_id == "beat_001"
    assert turn.state.node_id == "beat_001"
    assert bridge_active(turn.state)
    assert bridge_target_id(turn.state) == "beat_002"
    assert turn.state.pending_next_beat_id == "beat_002"
    assert "PONTE NARRATIVA" in turn.system_prompt
    assert "Você vem sempre aqui?" in turn.system_prompt
    assert "LINHA FUTURA PROIBIDA" in turn.system_prompt


def test_resposta_seguinte_libera_exatamente_o_beat_pendente() -> None:
    script = _script()
    bridge = decide_editorial_progression_turn(
        script,
        PilotState(),
        "Gostei do seu sorriso.",
    )

    canonical = decide_editorial_progression_turn(
        script,
        bridge.state,
        "Foi só um elogio sincero.",
    )

    assert canonical.target_id == "beat_002"
    assert canonical.state.node_id == "beat_002"
    assert not bridge_active(canonical.state)
    assert canonical.state.pending_next_beat_id == ""
    assert "Você vem sempre aqui?" in canonical.system_prompt


def test_ponte_nao_encadeia_outra_ponte_no_mesmo_avanco() -> None:
    script = _script()
    first_bridge = decide_editorial_progression_turn(script, PilotState(), "Olá, tudo bem?")
    canonical = decide_editorial_progression_turn(script, first_bridge.state, "Tudo sim.")

    assert canonical.target_id == "beat_002"
    assert not bridge_active(canonical.state)

    second_bridge = decide_editorial_progression_turn(script, canonical.state, "Venho às vezes.")
    assert second_bridge.target_id == "beat_002"
    assert bridge_active(second_bridge.state)
    assert bridge_target_id(second_bridge.state) == "beat_003"


def test_estado_de_ponte_sem_destino_falha_explicitamente() -> None:
    script = _script()
    broken = PilotState(node_id="beat_001", facts={"_runtime_phase": "bridge"})

    try:
        decide_editorial_progression_turn(script, broken, "Continuo.")
    except RuntimeError as exc:
        assert "sem beat alvo" in str(exc)
    else:
        raise AssertionError("Estado estrutural inválido não pode ser recuperado silenciosamente")
