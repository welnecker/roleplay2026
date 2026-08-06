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


def apply_psychological_deltas(
    state: Any,
    category: Mapping[str, Any] | None,
) -> Any:
    """Aplica deltas declarativos às dimensões existentes do estado.

    Cards podem usar ``state_deltas`` para qualquer dimensão numérica já
    exposta pelo estado. Os campos legados ``desire_delta`` e
    ``patience_delta`` continuam aceitos para preservar compatibilidade.
    """

    policy = dict(category or {})
    deltas = {
        str(key).strip(): int(value or 0)
        for key, value in dict(policy.get("state_deltas") or {}).items()
        if str(key).strip()
    }
    legacy = {
        "desire": int(policy.get("desire_delta", 0) or 0),
        "patience": int(policy.get("patience_delta", 0) or 0),
    }
    for key, value in legacy.items():
        if key not in deltas and value:
            deltas[key] = value

    for dimension_id, delta in deltas.items():
        if not hasattr(state, dimension_id):
            continue
        current = getattr(state, dimension_id)
        if isinstance(current, bool) or not isinstance(current, int):
            continue
        setattr(state, dimension_id, _bounded(current + delta))
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
    "apply_psychological_deltas",
    "psychological_dimensions",
    "render_psychological_state",
]
