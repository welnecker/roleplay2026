from __future__ import annotations

from services.editorial_metadata import (
    build_editorial_bridge_metadata,
    build_editorial_metadata,
    recover_editorial_state_payload,
)


def test_metadados_editoriais_sao_o_contrato_principal() -> None:
    metadata = build_editorial_metadata(
        node_id="beat_002",
        engagement="engaged",
        state={"node_id": "beat_002", "interest": 6},
        finished=False,
        run_status="active",
        ending_code="",
        diagnostics={"transition_reason": "normal_transition"},
    )

    assert metadata["editorial"] is True
    assert metadata["editorial_node"] == "beat_002"
    assert metadata["editorial_state"] == {"node_id": "beat_002", "interest": 6}
    assert metadata["editorial_run_status"] == "active"
    assert metadata["editorial_diagnostics"] == {
        "transition_reason": "normal_transition"
    }


def test_aliases_legados_sao_espelhos_temporarios() -> None:
    metadata = build_editorial_metadata(
        node_id="beat_end",
        engagement="engaged",
        state={"node_id": "beat_end", "finished": True},
        finished=True,
        run_status="completed",
        ending_code="success",
        diagnostics={"finished": True},
    )

    assert metadata["pilot_state"] is metadata["editorial_state"]
    assert metadata["pilot_node"] == metadata["editorial_node"]
    assert metadata["pilot_end_event"] == metadata["editorial_end_event"] == "END_RUN"
    assert metadata["pilot_run_status"] == metadata["editorial_run_status"]
    assert metadata["pilot_ending_code"] == metadata["editorial_ending_code"]


def test_aliases_legados_podem_ser_desligados_no_futuro() -> None:
    metadata = build_editorial_metadata(
        node_id="beat_003",
        engagement="minimal",
        state={"node_id": "beat_003"},
        finished=False,
        run_status="active",
        ending_code="",
        include_legacy_aliases=False,
    )

    assert "editorial_state" in metadata
    assert not any(key.startswith("pilot") for key in metadata)


def test_recuperacao_prioriza_estado_editorial() -> None:
    messages = [
        {"pilot_state": {"node_id": "legacy"}},
        {
            "editorial_state": {"node_id": "current"},
            "pilot_state": {"node_id": "mirror"},
        },
    ]

    assert recover_editorial_state_payload(messages) == {"node_id": "current"}


def test_recuperacao_aceita_save_legado() -> None:
    messages = [
        {"role": "assistant", "pilot_state": {"node_id": "legacy_beat"}}
    ]

    assert recover_editorial_state_payload(messages) == {"node_id": "legacy_beat"}


def test_bridge_usa_o_mesmo_contrato() -> None:
    metadata = build_editorial_bridge_metadata(
        node_id="bridge_001",
        state={"node_id": "bridge_001"},
    )

    assert metadata["editorial_engagement"] == "automatic_bridge"
    assert metadata["automatic_bridge"] is True
    assert metadata["editorial_end_event"] == ""
    assert metadata["editorial_run_status"] == "active"
