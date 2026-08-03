from __future__ import annotations

"""Contrato de persistência do runtime editorial.

Novas execuções escrevem chaves ``editorial_*``. Durante a migração, a leitura
aceita também o esquema histórico ``pilot_*`` para preservar saves existentes.
"""

from collections.abc import Mapping
from typing import Any


EDITORIAL_STATE_KEY = "editorial_state"
LEGACY_STATE_KEY = "pilot_state"


def recover_editorial_state_payload(
    messages: list[Mapping[str, object]],
) -> dict[str, Any] | None:
    """Retorna o estado persistido mais recente, priorizando o esquema atual."""

    for message in reversed(messages):
        current = message.get(EDITORIAL_STATE_KEY)
        if isinstance(current, dict):
            return dict(current)
        legacy = message.get(LEGACY_STATE_KEY)
        if isinstance(legacy, dict):
            return dict(legacy)
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
    include_legacy_aliases: bool = True,
) -> dict[str, object]:
    """Monta metadados canônicos e, temporariamente, aliases retrocompatíveis."""

    state_payload = dict(state)
    diagnostic_payload = dict(diagnostics or {})
    end_event = "END_RUN" if finished else ""
    metadata: dict[str, object] = {
        "editorial": True,
        "editorial_node": str(node_id),
        "editorial_engagement": str(engagement),
        EDITORIAL_STATE_KEY: state_payload,
        "editorial_end_event": end_event,
        "editorial_run_status": str(run_status),
        "editorial_ending_code": str(ending_code),
        "editorial_diagnostics": diagnostic_payload,
        "automatic_bridge": bool(automatic_bridge),
    }
    if include_legacy_aliases:
        metadata.update(
            {
                "pilot": True,
                "pilot_node": str(node_id),
                "pilot_engagement": str(engagement),
                LEGACY_STATE_KEY: state_payload,
                "pilot_end_event": end_event,
                "pilot_run_status": str(run_status),
                "pilot_ending_code": str(ending_code),
                "pilot_diagnostics": diagnostic_payload,
            }
        )
    return metadata


def build_editorial_bridge_metadata(
    *,
    node_id: str,
    state: Mapping[str, object],
    include_legacy_aliases: bool = True,
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
        include_legacy_aliases=include_legacy_aliases,
    )


__all__ = [
    "EDITORIAL_STATE_KEY",
    "LEGACY_STATE_KEY",
    "build_editorial_bridge_metadata",
    "build_editorial_metadata",
    "recover_editorial_state_payload",
]
