from __future__ import annotations

"""Contrato canônico de persistência do runtime editorial."""

from collections.abc import Mapping
from typing import Any


EDITORIAL_STATE_KEY = "editorial_state"


def recover_editorial_state_payload(
    messages: list[Mapping[str, object]],
) -> dict[str, Any] | None:
    """Retorna o estado editorial persistido mais recente."""

    for message in reversed(messages):
        current = message.get(EDITORIAL_STATE_KEY)
        if isinstance(current, dict):
            return dict(current)
    return None


def build_editorial_metadata(
    *,
    node_id: str,
    engagement: str,
    state: Mapping[str, object],
    finished: bool,
    run_status: str,
    ending_code: str,
    diagnostics: Mapping[str, object] | None = None,
    automatic_bridge: bool = False,
) -> dict[str, object]:
    """Monta os metadados canônicos de uma mensagem editorial."""

    return {
        "editorial": True,
        "editorial_node": str(node_id),
        "editorial_engagement": str(engagement),
        EDITORIAL_STATE_KEY: dict(state),
        "editorial_end_event": "END_RUN" if finished else "",
        "editorial_run_status": str(run_status),
        "editorial_ending_code": str(ending_code),
        "editorial_diagnostics": dict(diagnostics or {}),
        "automatic_bridge": bool(automatic_bridge),
    }


def build_editorial_bridge_metadata(
    *,
    node_id: str,
    state: Mapping[str, object],
) -> dict[str, object]:
    return build_editorial_metadata(
        node_id=node_id,
        engagement="automatic_bridge",
        state=state,
        finished=False,
        run_status="active",
        ending_code="",
        diagnostics=None,
        automatic_bridge=True,
    )


__all__ = [
    "EDITORIAL_STATE_KEY",
    "build_editorial_bridge_metadata",
    "build_editorial_metadata",
    "recover_editorial_state_payload",
]
