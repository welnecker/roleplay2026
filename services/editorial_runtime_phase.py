from __future__ import annotations

from typing import Any, Mapping


_PHASE_KEY = "_runtime_phase"
_BRIDGE_ORIGIN_KEY = "_bridge_origin_beat_id"
_BRIDGE_TARGET_KEY = "_bridge_target_beat_id"
_CONTEXTUAL_ROUTE_KEY = "_contextual_route"
_CONTEXTUAL_SIGNAL_KEY = "_contextual_signal"
_CONTEXTUAL_REASON_KEY = "_contextual_reason"
_CONTEXTUAL_CONFIDENCE_KEY = "_contextual_confidence"


def _facts(state: Any) -> Mapping[str, object]:
    value = getattr(state, "facts", {}) or {}
    return value if isinstance(value, Mapping) else {}


def runtime_phase(state: Any) -> str:
    facts = _facts(state)
    declared = str(facts.get(_PHASE_KEY, "") or "").strip()
    if declared in {"canonical", "bridge", "terminal_yard"}:
        return declared
    if str(facts.get("_terminal_yard_id", "") or "").strip():
        return "terminal_yard"
    return "canonical"


def runtime_phase_metadata(state: Any) -> dict[str, object]:
    facts = _facts(state)
    return {
        "runtime_phase": runtime_phase(state),
        "bridge_origin_beat_id": str(facts.get(_BRIDGE_ORIGIN_KEY, "") or ""),
        "bridge_target_beat_id": str(facts.get(_BRIDGE_TARGET_KEY, "") or ""),
        "contextual_route": str(facts.get(_CONTEXTUAL_ROUTE_KEY, "") or ""),
        "contextual_signal": str(facts.get(_CONTEXTUAL_SIGNAL_KEY, "") or ""),
        "contextual_reason": str(facts.get(_CONTEXTUAL_REASON_KEY, "") or ""),
        "contextual_confidence": str(facts.get(_CONTEXTUAL_CONFIDENCE_KEY, "") or ""),
    }


__all__ = ["runtime_phase", "runtime_phase_metadata"]
