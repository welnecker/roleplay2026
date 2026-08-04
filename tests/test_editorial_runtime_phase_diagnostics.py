from __future__ import annotations

from services.editorial_diagnostics import build_editorial_turn_diagnostics
from services.editorial_runtime_phase import runtime_phase, runtime_phase_metadata
from services.editorial_runtime_types import EditorialState, EditorialTurn


def _turn(state: EditorialState) -> EditorialTurn:
    return EditorialTurn(
        engagement="engaged",
        target_id=state.node_id,
        visible_fallback="",
        system_prompt="",
        state=state,
    )


def test_estado_sem_fase_permanece_canonico() -> None:
    state = EditorialState(node_id="beat_001")

    assert runtime_phase(state) == "canonical"
    assert runtime_phase_metadata(state)["runtime_phase"] == "canonical"


def test_metadados_da_ponte_expoem_origem_alvo_e_contexto() -> None:
    state = EditorialState(
        node_id="beat_001",
        facts={
            "_runtime_phase": "bridge",
            "_bridge_origin_beat_id": "beat_001",
            "_bridge_target_beat_id": "beat_002",
            "_contextual_route": "continue",
            "_contextual_signal": "interest",
            "_contextual_reason": "resposta aberta",
            "_contextual_confidence": "0.920",
        },
    )

    metadata = runtime_phase_metadata(state)

    assert metadata == {
        "runtime_phase": "bridge",
        "bridge_origin_beat_id": "beat_001",
        "bridge_target_beat_id": "beat_002",
        "contextual_route": "continue",
        "contextual_signal": "interest",
        "contextual_reason": "resposta aberta",
        "contextual_confidence": "0.920",
    }


def test_diagnostico_publico_identifica_ponte_estrutural() -> None:
    previous = EditorialState(node_id="beat_001")
    resulting = EditorialState(
        node_id="beat_001",
        pending_next_beat_id="beat_002",
        facts={
            "_runtime_phase": "bridge",
            "_bridge_origin_beat_id": "beat_001",
            "_bridge_target_beat_id": "beat_002",
        },
    )

    diagnostics = build_editorial_turn_diagnostics(
        user_text="continue",
        previous_state=previous,
        turn=_turn(resulting),
        raw_model_response="resposta",
        final_response="resposta",
        fallback="",
    )

    assert diagnostics["diagnostic_version"] == 4
    assert diagnostics["runtime_phase"] == "bridge"
    assert diagnostics["transition_reason"] == "structural_bridge"
    assert diagnostics["bridge_origin_beat_id"] == "beat_001"
    assert diagnostics["bridge_target_beat_id"] == "beat_002"


def test_diagnostico_identifica_patio_terminal() -> None:
    previous = EditorialState(node_id="yard_001")
    resulting = EditorialState(
        node_id="yard_002",
        facts={"_runtime_phase": "terminal_yard"},
    )

    diagnostics = build_editorial_turn_diagnostics(
        user_text="entendi",
        previous_state=previous,
        turn=_turn(resulting),
        raw_model_response="resposta",
        final_response="resposta",
        fallback="",
    )

    assert diagnostics["runtime_phase"] == "terminal_yard"
    assert diagnostics["transition_reason"] == "terminal_yard"
