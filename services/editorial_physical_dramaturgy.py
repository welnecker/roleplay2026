from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping


_LAST_IDS_KEY = "_last_physical_dramaturgy_ids"
_ACTIVE_IDS_KEY = "_active_physical_dramaturgy_ids"


@dataclass(frozen=True, slots=True)
class ActivePhysicalDramaturgy:
    aspect_id: str
    trait: str
    dramatic_function: str
    expression_options: tuple[str, ...]
    avoid: tuple[str, ...]
    priority: int


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("physical_dramaturgy") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("physical_dramaturgy") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _normalized_pattern(pattern: str) -> str:
    return str(pattern).replace("\\\\", "\\")


def _matches_patterns(text: str, patterns: Any) -> bool:
    declared = _items(patterns)
    if not declared:
        return True
    for pattern in declared:
        try:
            if re.search(_normalized_pattern(pattern), text, flags=re.IGNORECASE):
                return True
        except re.error as exc:
            raise ValueError(f"Regex inválida em physical_dramaturgy: {exc}") from exc
    return False


def _matches_scope(definition: Mapping[str, Any], target: Mapping[str, Any]) -> bool:
    block_ids = set(_items(definition.get("block_ids")))
    beat_prefixes = _items(definition.get("beat_prefixes"))
    beat_ids = set(_items(definition.get("beat_ids")))
    if not block_ids and not beat_prefixes and not beat_ids:
        return True
    block_id = str(target.get("block_id", "") or "")
    beat_id = str(target.get("beat_id", target.get("ending_id", "")) or "")
    return (
        block_id in block_ids
        or beat_id in beat_ids
        or any(beat_id.startswith(prefix) for prefix in beat_prefixes)
    )


def _matches_dimensions(state: Any, dimensions: Any) -> bool:
    if not dimensions:
        return True
    if not isinstance(dimensions, dict):
        return False
    for dimension_id, raw in dimensions.items():
        if not hasattr(state, str(dimension_id)) or not isinstance(raw, dict):
            return False
        value = int(getattr(state, str(dimension_id)))
        minimum = int(raw.get("min", 0) or 0)
        maximum = int(raw.get("max", 10) or 10)
        if not minimum <= value <= maximum:
            return False
    return True


def select_physical_dramaturgy(
    document: Mapping[str, Any],
    state: Any,
    target: Mapping[str, Any],
    context_text: str,
    engagement: str,
) -> list[ActivePhysicalDramaturgy]:
    """Seleciona traços físicos apenas quando têm função dramática no turno."""

    policy = _policy(document)
    aspects = policy.get("aspects") or {}
    if not isinstance(aspects, dict):
        return []

    physical_profile = {
        str(item).strip()
        for item in ((document.get("character") or {}).get("physical_profile") or [])
        if str(item).strip()
    }
    previous_ids = {
        item.strip()
        for item in str(state.facts.get(_LAST_IDS_KEY, "") or "").split(",")
        if item.strip()
    }
    candidates: list[ActivePhysicalDramaturgy] = []
    for aspect_id, raw in aspects.items():
        if not isinstance(raw, dict):
            continue
        trait = str(raw.get("trait", "") or "").strip()
        if not trait or trait not in physical_profile:
            raise ValueError(
                f"physical_dramaturgy.{aspect_id} referencia traço ausente em character.physical_profile: {trait!r}"
            )
        engagements = set(_items(raw.get("engagements")))
        if engagements and str(engagement) not in engagements:
            continue
        if not _matches_scope(raw, target):
            continue
        if not _matches_dimensions(state, raw.get("dimensions")):
            continue
        if not _matches_patterns(context_text, raw.get("context_patterns")):
            continue
        dramatic_function = str(raw.get("dramatic_function", "") or "").strip()
        if not dramatic_function:
            continue
        candidates.append(
            ActivePhysicalDramaturgy(
                aspect_id=str(aspect_id),
                trait=trait,
                dramatic_function=dramatic_function,
                expression_options=_items(raw.get("expression_options")),
                avoid=_items(raw.get("avoid")),
                priority=int(raw.get("priority", 5) or 5),
            )
        )

    candidates.sort(
        key=lambda item: (
            item.aspect_id in previous_ids,
            -item.priority,
            item.aspect_id,
        )
    )
    maximum = max(0, int(policy.get("max_active_aspects", 2) or 2))
    selected = candidates[:maximum] if maximum else []
    state.facts[_ACTIVE_IDS_KEY] = ",".join(item.aspect_id for item in selected)
    state.facts[_LAST_IDS_KEY] = state.facts[_ACTIVE_IDS_KEY]
    return selected


def render_physical_dramaturgy(aspects: list[ActivePhysicalDramaturgy]) -> str:
    if not aspects:
        return ""
    lines = ["USO DRAMÁTICO DO PERFIL FÍSICO E CORPORAL:"]
    for item in aspects:
        lines.append(f"- {item.dramatic_function}")
        lines.extend(f"  Pode aparecer por: {option}" for option in item.expression_options)
        lines.extend(f"  Evite: {warning}" for warning in item.avoid)
    lines.extend(
        (
            "REGRAS:",
            "- Use no máximo um detalhe corporal por movimento de fala; não recite o perfil físico.",
            "- O corpo deve revelar tensão, escolha, vulnerabilidade ou iniciativa, nunca funcionar como decoração repetitiva.",
            "- Não invente roupa, posição, toque, deslocamento ou exposição corporal que o beat e a cena não autorizem.",
            "- Quando a política do turno restringir narração física, converta o efeito em ritmo, silêncio, escolha de palavras ou autoconsciência na fala.",
            "- Não descreva ações do usuário nem trate a reação corporal dele como fato.",
            "- Não mencione aspectos, seleção, perfil ou regras internas.",
        )
    )
    return "\n".join(lines)


__all__ = [
    "ActivePhysicalDramaturgy",
    "render_physical_dramaturgy",
    "select_physical_dramaturgy",
]
