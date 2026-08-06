from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn

_RESOLVED_TOPICS_KEY = "_resolved_topic_ids"


def _clean_ids(values: Iterable[object]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def resolved_topic_ids(state: EditorialState) -> list[str]:
    raw = str(state.facts.get(_RESOLVED_TOPICS_KEY, "") or "")
    return [item.strip() for item in raw.split(",") if item.strip()]


def _topics_resolved_on_exit(beat: dict[str, Any]) -> list[str]:
    configured = beat.get("resolve_topics_on_exit")
    if configured is None:
        configured = beat.get("resolve_topic_on_exit")
    if isinstance(configured, str):
        return [configured.strip()] if configured.strip() else []
    if isinstance(configured, (list, tuple, set)):
        return _clean_ids(configured)
    return []


def apply_resolved_topics(
    script: EditorialScript,
    previous_state: EditorialState,
    turn: EditorialTurn,
) -> EditorialTurn:
    """Resolve assuntos declarados quando o turno realmente deixa o beat de origem.

    O motor não conhece o significado do assunto. Cada card declara apenas um ID
    estável e escolhe em qual transição ele deixa de estar aberto.
    """

    origin_id = str(previous_state.node_id or script.first_beat_id).strip()
    target_id = str(turn.target_id or "").strip()
    if not origin_id or not target_id or target_id == origin_id or turn.finished:
        return turn

    origin = script.beats.get(origin_id) or {}
    newly_resolved = _topics_resolved_on_exit(origin)
    if not newly_resolved:
        return turn

    updated = EditorialState.from_dict(turn.state.to_dict())
    merged = list(dict.fromkeys([*resolved_topic_ids(updated), *newly_resolved]))
    updated.facts[_RESOLVED_TOPICS_KEY] = ",".join(merged)
    return replace(turn, state=updated)


def _topic_catalog(script: EditorialScript) -> dict[str, Any]:
    policy = script.raw.get("runtime_policy") or {}
    if not isinstance(policy, dict):
        return {}
    resolution = policy.get("topic_resolution") or {}
    if not isinstance(resolution, dict):
        return {}
    catalog = resolution.get("topics") or {}
    return catalog if isinstance(catalog, dict) else {}


def render_resolved_topic_guard(
    script: EditorialScript,
    state: EditorialState,
) -> str:
    ids = resolved_topic_ids(state)
    if not ids:
        return ""

    catalog = _topic_catalog(script)
    descriptions: list[str] = []
    for topic_id in ids:
        item = catalog.get(topic_id) or {}
        if isinstance(item, dict):
            description = str(item.get("description", "") or "").strip()
        else:
            description = str(item or "").strip()
        descriptions.append(description or topic_id)

    rendered = "\n".join(f"- {description}" for description in descriptions)
    return (
        "ASSUNTOS JÁ RESOLVIDOS — NÃO REABRIR:\n"
        f"{rendered}\n"
        "- Pode haver uma referência mínima de ligação, mas não peça nova confirmação, "
        "não repita a preocupação e não transforme o assunto resolvido em novo obstáculo."
    )


__all__ = [
    "apply_resolved_topics",
    "render_resolved_topic_guard",
    "resolved_topic_ids",
]
