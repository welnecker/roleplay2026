from __future__ import annotations

from services.editorial_metadata import (
    build_editorial_bridge_metadata,
    build_editorial_metadata,
    recover_editorial_state_payload,
)


def test_metadados_editoriais_sao_o_unico_contrato() -> None:
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
    assert not any(key.startswith("pilot") for key in metadata)


def test_encerramento_usa_evento_editorial() -> None:
    metadata = build_editorial_metadata(
        node_id="beat_end",
        engagement="engaged",
        state={"node_id": "beat_end", "finished": True},
        finished=True,
        run_status="completed",
        ending_code="success",
        diagnostics={"finished": True},
    )

    assert metadata["editorial_end_event"] == "END_RUN"
    assert metadata["editorial_run_status"] == "completed"
    assert metadata["editorial_ending_code"] == "success"


def test_recuperacao_considera_apenas_estado_editorial() -> None:
    messages = [
        {"pilot_state": {"node_id": "ignored"}},
        {"editorial_state": {"node_id": "current"}},
    ]

    assert recover_editorial_state_payload(messages) == {"node_id": "current"}


def test_recuperacao_sem_estado_editorial_retorna_none() -> None:
    messages = [
        {"role": "assistant", "pilot_state": {"node_id": "legacy_beat"}}
    ]

    assert recover_editorial_state_payload(messages) is None


def test_bridge_usa_o_mesmo_contrato() -> None:
    metadata = build_editorial_bridge_metadata(
        node_id="bridge_001",
        state={"node_id": "bridge_001"},
    )

    assert metadata["editorial_engagement"] == "automatic_bridge"
    assert metadata["automatic_bridge"] is True
    assert metadata["editorial_end_event"] == ""
    assert metadata["editorial_run_status"] == "active"
    assert not any(key.startswith("pilot") for key in metadata)
