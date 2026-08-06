from __future__ import annotations

import json
import re
from typing import Any, Mapping

from services.editorial_memory_ui import clear_memory_request, peek_memory_request

_TURN_KEY = "_episodic_memory_turn"
_REQUEST_KEY = "_memory_requested"
_DRAFT_KEY = "_selected_memory_draft_json"
_THREADS_KEY = "_continuity_memories_json"
_RECOLLECTIONS_KEY = "_relationship_recollections_json"

_THOUGHT_PATTERN = re.compile(
    r"\[PENSAMENTO\].*?\[/PENSAMENTO\]",
    flags=re.IGNORECASE | re.DOTALL,
)


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("episodic_memory") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    runtime = document.get("runtime_policy") or {}
    nested = runtime.get("episodic_memory") if isinstance(runtime, dict) else {}
    return dict(nested) if isinstance(nested, dict) else {}


def _load_list(value: object) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [dict(item) for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _load_dict(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _clean(text: str, limit: int = 320) -> str:
    return " ".join(str(text or "").split()).strip()[:limit]


def _visible(text: str, limit: int = 240) -> str:
    return _clean(_THOUGHT_PATTERN.sub("", str(text or "")), limit)


def mark_memory_requested(facts: dict[str, str], requested: bool) -> None:
    facts[_REQUEST_KEY] = "true" if requested else "false"


def memory_requested(facts: Mapping[str, str]) -> bool:
    selected_in_state = str(facts.get(_REQUEST_KEY, "false") or "false").lower() == "true"
    return selected_in_state or peek_memory_request()


def advance_episode_turn(document: Mapping[str, Any], facts: dict[str, str]) -> int:
    if not _policy(document):
        return 0
    value = int(facts.get(_TURN_KEY, "0") or 0) + 1
    facts[_TURN_KEY] = str(value)
    return value


def prepare_selected_memory(
    document: Mapping[str, Any],
    facts: dict[str, str],
    user_text: str,
    *,
    source_beat_id: str,
    runtime_phase: str,
) -> str:
    """Prepara somente memórias explicitamente marcadas pelo usuário.

    A fase estrutural elimina a ambiguidade:
    bridge -> fio de continuidade consumível;
    canonical -> lembrança cotidiana persistente.
    """

    policy = _policy(document)
    text = _clean(user_text)
    if not policy or not text or not memory_requested(facts):
        facts.pop(_DRAFT_KEY, None)
        return "ignored"

    kind = "continuity" if str(runtime_phase or "") == "bridge" else "recollection"
    turn = int(facts.get(_TURN_KEY, "0") or 0)
    facts[_DRAFT_KEY] = _dump(
        {
            "kind": kind,
            "user_text": text,
            "source_beat_id": str(source_beat_id or ""),
            "turn": turn,
        }
    )
    facts[_REQUEST_KEY] = "false"
    return kind


def _next_id(prefix: str, items: list[dict[str, Any]]) -> str:
    highest = 0
    for item in items:
        match = re.search(r"(\d+)$", str(item.get("memory_id", "")))
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}_{highest + 1:03d}"


def consolidate_selected_memory(facts: dict[str, str], assistant_text: str) -> None:
    """Consolida a memória somente depois da resposta de Mary ser aprovada."""

    draft = _load_dict(facts.pop(_DRAFT_KEY, ""))
    if not draft:
        return
    user_text = _clean(str(draft.get("user_text", "")))
    mary_text = _visible(assistant_text)
    if not user_text or not mary_text:
        return

    if draft.get("kind") == "continuity":
        threads = _load_list(facts.get(_THREADS_KEY, ""))
        threads.append(
            {
                "memory_id": _next_id("thread", threads),
                "type": "continuity",
                "user_text": user_text,
                "mary_text": mary_text,
                "source_beat_id": str(draft.get("source_beat_id", "")),
                "created_at_turn": int(draft.get("turn", 0) or 0),
                "status": "available",
            }
        )
        facts[_THREADS_KEY] = _dump(threads)
    else:
        recollections = _load_list(facts.get(_RECOLLECTIONS_KEY, ""))
        recollections.append(
            {
                "memory_id": _next_id("recollection", recollections),
                "type": "relationship_recollection",
                "text": f'Usuário: "{user_text}" | Mary: "{mary_text}"',
                "source_beat_id": str(draft.get("source_beat_id", "")),
                "created_at_turn": int(draft.get("turn", 0) or 0),
                "status": "active",
            }
        )
        facts[_RECOLLECTIONS_KEY] = _dump(recollections[-20:])

    clear_memory_request()


def _recall_allowed(policy: Mapping[str, Any], beat_id: str) -> bool:
    rules = policy.get("recall", []) or []
    if not rules:
        return False
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        beat_ids = {str(item) for item in rule.get("beat_ids", []) or []}
        prefixes = tuple(str(item) for item in rule.get("beat_prefixes", []) or [])
        if beat_id in beat_ids or any(beat_id.startswith(prefix) for prefix in prefixes):
            return True
    return False


def recall_episode(
    document: Mapping[str, Any],
    facts: dict[str, str],
    *,
    beat_id: str,
) -> str:
    """Entrega ao beat no máximo um fio e o consome de forma determinística."""

    policy = _policy(document)
    clean_beat_id = str(beat_id or "").strip()
    if not policy or not _recall_allowed(policy, clean_beat_id):
        return ""

    threads = _load_list(facts.get(_THREADS_KEY, ""))
    selected: dict[str, Any] | None = None
    for item in threads:
        if item.get("status") == "available" and clean_beat_id != str(item.get("source_beat_id", "")):
            selected = item
            break
    if selected is None:
        return ""

    selected["status"] = "consumed"
    selected["consumed_at_beat_id"] = clean_beat_id
    selected["consumed_at_turn"] = int(facts.get(_TURN_KEY, "0") or 0)
    facts[_THREADS_KEY] = _dump(threads)
    return (
        f'Usuário: "{selected.get("user_text", "")}" | '
        f'Mary: "{selected.get("mary_text", "")}"'
    )


def render_relationship_recollections(facts: Mapping[str, str], *, maximum: int = 12) -> str:
    items = [
        str(item.get("text", "")).strip()
        for item in _load_list(facts.get(_RECOLLECTIONS_KEY, ""))
        if item.get("status") == "active" and str(item.get("text", "")).strip()
    ]
    if not items:
        return ""
    return "LEMBRANÇAS COTIDIANAS ESCOLHIDAS PELO USUÁRIO:\n" + "\n".join(
        f"- {text}" for text in items[-max(1, maximum):]
    )


def continuity_memories(facts: Mapping[str, str]) -> list[dict[str, Any]]:
    return _load_list(facts.get(_THREADS_KEY, ""))


def relationship_recollections(facts: Mapping[str, str]) -> list[dict[str, Any]]:
    return _load_list(facts.get(_RECOLLECTIONS_KEY, ""))


# Compatibilidade temporária com chamadas antigas da branch.
def prepare_bridge_episode(
    document: Mapping[str, Any],
    facts: dict[str, str],
    user_text: str,
    *,
    source_beat_id: str,
) -> str:
    return prepare_selected_memory(
        document,
        facts,
        user_text,
        source_beat_id=source_beat_id,
        runtime_phase="bridge",
    )


def consolidate_bridge_episode(facts: dict[str, str], assistant_text: str) -> None:
    consolidate_selected_memory(facts, assistant_text)


def creativity_blocked(_facts: Mapping[str, str]) -> bool:
    return False


__all__ = [
    "advance_episode_turn",
    "consolidate_bridge_episode",
    "consolidate_selected_memory",
    "continuity_memories",
    "creativity_blocked",
    "mark_memory_requested",
    "memory_requested",
    "prepare_bridge_episode",
    "prepare_selected_memory",
    "recall_episode",
    "relationship_recollections",
    "render_relationship_recollections",
]
