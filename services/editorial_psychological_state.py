from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class PsychologicalDimension:
    dimension_id: str
    label: str
    value: int
    band_id: str
    effect: str


def _bounded(value: Any, *, minimum: int = 0, maximum: int = 10) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("psychological_state") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("psychological_state") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _apply_deltas(state: Any, deltas: Mapping[str, Any]) -> Any:
    for dimension_id, raw_delta in deltas.items():
        dimension_id = str(dimension_id).strip()
        if not dimension_id or not hasattr(state, dimension_id):
            continue
        current = getattr(state, dimension_id)
        if isinstance(current, bool) or not isinstance(current, int):
            continue
        try:
            delta = int(raw_delta or 0)
        except (TypeError, ValueError):
            continue
        setattr(state, dimension_id, _bounded(current + delta))
    return state


def apply_psychological_deltas(
    state: Any,
    category: Mapping[str, Any] | None,
) -> Any:
    """Aplica deltas declarativos e preserva o contrato legado do runtime."""

    policy = dict(category or {})
    deltas = dict(policy.get("state_deltas") or {})
    legacy = {
        "desire": int(policy.get("desire_delta", 0) or 0),
        "patience": int(policy.get("patience_delta", 0) or 0),
    }
    for key, value in legacy.items():
        if key not in deltas and value:
            deltas[key] = value
    return _apply_deltas(state, deltas)


def apply_card_psychological_deltas(
    document: Mapping[str, Any],
    state: Any,
    engagement: str,
) -> Any:
    """Evolui o estado conforme regras pertencentes ao card.

    A aplicação é idempotente por turno editorial para evitar que pontes ou
    finalizações repetidas alterem a psicologia mais de uma vez.
    """

    policy = _policy(document)
    declared = policy.get("engagement_deltas") or {}
    if not isinstance(declared, dict):
        return state
    turn_key = str(state.facts.get("_psychological_delta_turn", "") or "")
    fingerprint = f"{state.node_id}:{len(state.recent_engagement)}:{engagement}"
    if turn_key == fingerprint:
        return state
    deltas = declared.get(str(engagement)) or {}
    if isinstance(deltas, dict):
        _apply_deltas(state, deltas)
    state.facts["_psychological_delta_turn"] = fingerprint
    return state


def _band_for_value(definition: Mapping[str, Any], value: int) -> tuple[str, str]:
    bands = definition.get("bands") or []
    if isinstance(bands, dict):
        iterable = [
            {"band_id": str(band_id), **dict(item)}
            for band_id, item in bands.items()
            if isinstance(item, dict)
        ]
    elif isinstance(bands, list):
        iterable = [dict(item) for item in bands if isinstance(item, dict)]
    else:
        iterable = []

    for index, band in enumerate(iterable):
        minimum = _bounded(band.get("min", 0))
        maximum = _bounded(band.get("max", 10))
        if minimum <= value <= maximum:
            band_id = str(band.get("band_id", f"band_{index + 1}") or f"band_{index + 1}")
            effect = str(band.get("effect", "") or "").strip()
            return band_id, effect
    return "unclassified", ""


def psychological_dimensions(document: Mapping[str, Any], state: Any) -> list[PsychologicalDimension]:
    policy = _policy(document)
    dimensions = policy.get("dimensions") or {}
    if not isinstance(dimensions, dict):
        return []

    rendered: list[PsychologicalDimension] = []
    for dimension_id, raw_definition in dimensions.items():
        if not isinstance(raw_definition, dict) or not hasattr(state, str(dimension_id)):
            continue
        value = _bounded(getattr(state, str(dimension_id)))
        band_id, effect = _band_for_value(raw_definition, value)
        if not effect:
            continue
        rendered.append(
            PsychologicalDimension(
                dimension_id=str(dimension_id),
                label=str(raw_definition.get("label", dimension_id) or dimension_id),
                value=value,
                band_id=band_id,
                effect=effect,
            )
        )
    return rendered


def render_psychological_state(document: Mapping[str, Any], state: Any) -> str:
    policy = _policy(document)
    if not policy:
        return ""

    dimensions = psychological_dimensions(document, state)
    if not dimensions:
        return ""

    title = str(policy.get("title", "ESTADO PSICOLÓGICO ATUAL") or "ESTADO PSICOLÓGICO ATUAL")
    rules = [
        str(item).strip()
        for item in policy.get("expression_rules", []) or []
        if str(item).strip()
    ]
    lines = [f"{title}:"]
    lines.extend(f"- {item.label}: {item.effect}" for item in dimensions)
    if rules:
        lines.append("EFEITO VISÍVEL OBRIGATÓRIO:")
        lines.extend(f"- {rule}" for rule in rules)
    return "\n".join(lines)


__all__ = [
    "PsychologicalDimension",
    "apply_card_psychological_deltas",
    "apply_psychological_deltas",
    "psychological_dimensions",
    "render_psychological_state",
]
