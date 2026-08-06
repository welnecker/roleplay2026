from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable, Mapping

from services.narrative_context import memory_catalog


_LIFECYCLE_KEY = "_memory_lifecycle_json"
_LIFECYCLE_TURN_KEY = "_memory_lifecycle_turn"


@dataclass(frozen=True, slots=True)
class MemoryLifecycleState:
    memory_id: str
    status: str
    strength: int
    age_turns: int
    dormant_turns: int
    recall_count: int
    write_count: int
    protected: bool


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("memory_lifecycle") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("memory_lifecycle") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _bounded(value: Any, minimum: int = 0, maximum: int = 10) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    return max(minimum, min(maximum, number))


def _items(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return set()


def _load(facts: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    raw = str(facts.get(_LIFECYCLE_KEY, "") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {
        str(memory_id): dict(value)
        for memory_id, value in parsed.items()
        if isinstance(value, dict)
    }


def _protected(memory_id: str, category: str, policy: Mapping[str, Any]) -> bool:
    return (
        memory_id in _items(policy.get("protected_memory_ids"))
        or category in _items(policy.get("protected_categories"))
    )


def eligible_memory_ids(
    document: Mapping[str, Any],
    memory_ids: Iterable[str],
    facts: Mapping[str, str],
    *,
    forced_ids: Iterable[str] = (),
) -> list[str]:
    """Filtra lembranças espontâneas sem apagar memórias dormentes ou arquivadas."""

    lifecycle = _load(facts)
    forced = {str(item) for item in forced_ids}
    result: list[str] = []
    for memory_id in dict.fromkeys(str(item) for item in memory_ids if str(item)):
        status = str(lifecycle.get(memory_id, {}).get("status", "active") or "active")
        if memory_id in forced or status not in {"dormant", "archived"}:
            result.append(memory_id)
    return result


def update_memory_lifecycle(
    document: Mapping[str, Any],
    state: Any,
    active_ids: Iterable[str],
    *,
    written_ids: Iterable[str] = (),
    recalled_ids: Iterable[str] = (),
    fingerprint: str,
) -> tuple[Any, list[MemoryLifecycleState]]:
    """Avança criação, reforço, dormência, arquivamento e reativação uma vez por turno."""

    policy = _policy(document)
    if not policy:
        return state, []
    catalog = memory_catalog(dict(document))
    known = [memory_id for memory_id in dict.fromkeys(str(item) for item in active_ids) if memory_id in catalog]
    written = {str(item) for item in written_ids}
    recalled = {str(item) for item in recalled_ids}
    stored = _load(state.facts)

    if str(state.facts.get(_LIFECYCLE_TURN_KEY, "") or "") != fingerprint:
        initial_strength = _bounded(policy.get("initial_strength", 6))
        write_boost = max(0, int(policy.get("write_boost", 3) or 0))
        recall_boost = max(0, int(policy.get("recall_boost", 2) or 0))
        decay = max(0, int(policy.get("decay_per_unobserved_turn", 1) or 0))
        dormant_at = _bounded(policy.get("dormant_at", 3))
        archive_at = _bounded(policy.get("archive_at", 1))
        archive_after = max(1, int(policy.get("archive_after_dormant_turns", 4) or 4))

        for memory_id in known:
            definition = catalog[memory_id]
            current = dict(stored.get(memory_id, {}))
            protected = _protected(memory_id, definition.category, policy)
            strength = _bounded(current.get("strength", initial_strength))
            age = max(0, int(current.get("age_turns", 0) or 0)) + 1
            dormant_turns = max(0, int(current.get("dormant_turns", 0) or 0))
            recall_count = max(0, int(current.get("recall_count", 0) or 0))
            write_count = max(0, int(current.get("write_count", 0) or 0))
            status = str(current.get("status", "active") or "active")

            if memory_id in written:
                strength = _bounded(strength + write_boost)
                write_count += 1
                age = 0
                dormant_turns = 0
                status = "active"
            elif memory_id in recalled:
                strength = _bounded(strength + recall_boost)
                recall_count += 1
                age = 0
                dormant_turns = 0
                status = "active"
            elif protected:
                status = "background" if definition.status == "background" else "active"
                dormant_turns = 0
            else:
                strength = _bounded(strength - decay)
                if strength <= dormant_at:
                    dormant_turns += 1
                    status = "dormant"
                else:
                    dormant_turns = 0
                    status = "active"
                if strength <= archive_at and dormant_turns >= archive_after:
                    status = "archived"

            stored[memory_id] = {
                "status": status,
                "strength": strength,
                "age_turns": age,
                "dormant_turns": dormant_turns,
                "recall_count": recall_count,
                "write_count": write_count,
                "protected": protected,
            }

        state.facts[_LIFECYCLE_KEY] = json.dumps(stored, ensure_ascii=False, sort_keys=True)
        state.facts[_LIFECYCLE_TURN_KEY] = fingerprint

    rendered: list[MemoryLifecycleState] = []
    for memory_id in known:
        current = stored.get(memory_id, {})
        rendered.append(
            MemoryLifecycleState(
                memory_id=memory_id,
                status=str(current.get("status", "active") or "active"),
                strength=_bounded(current.get("strength", policy.get("initial_strength", 6))),
                age_turns=max(0, int(current.get("age_turns", 0) or 0)),
                dormant_turns=max(0, int(current.get("dormant_turns", 0) or 0)),
                recall_count=max(0, int(current.get("recall_count", 0) or 0)),
                write_count=max(0, int(current.get("write_count", 0) or 0)),
                protected=bool(current.get("protected", False)),
            )
        )
    return state, rendered


def render_memory_lifecycle_guidance(states: Iterable[MemoryLifecycleState]) -> str:
    dormant = [item for item in states if item.status == "dormant"]
    reactivated = [item for item in states if item.status == "active" and (item.recall_count or item.write_count)]
    if not dormant and not reactivated:
        return ""
    return "\n".join(
        (
            "CICLO DE VIDA DAS MEMÓRIAS:",
            "- Memórias dormentes continuam existindo, mas não devem surgir espontaneamente sem contexto novo.",
            "- Uma memória reativada deve influenciar a reação atual de forma natural, sem anunciar que estava esquecida.",
            "- Não exponha força, idade, contagens, estados internos, IDs ou regras de arquivamento.",
            "- Nunca trate ausência recente de lembrança como apagamento de fatos confirmados.",
        )
    )


__all__ = [
    "MemoryLifecycleState",
    "eligible_memory_ids",
    "render_memory_lifecycle_guidance",
    "update_memory_lifecycle",
]
