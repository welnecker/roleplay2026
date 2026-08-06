from __future__ import annotations

import json
import re
from typing import Any, Mapping

_STORE_KEY = "_episodic_memory_json"
_RECALLED_KEY = "_episodic_memory_recalled_id"
_SEQ_KEY = "_episodic_memory_sequence"

_TAG_PATTERNS = {
    "action": re.compile(r"\ba[cç][aã]o\b", re.IGNORECASE),
    "initiative": re.compile(r"\b(?:atitude|iniciativa|agir|diret[oa])\b", re.IGNORECASE),
    "desire": re.compile(r"\b(?:quero|queria|gostaria|vontade|desejo|tes[aã]o)\b", re.IGNORECASE),
    "lingerie": re.compile(r"\b(?:calcinha|suti[aã]|lingerie)\b", re.IGNORECASE),
    "phone": re.compile(r"\b(?:telefone|celular|n[uú]mero|liga|mensagem|v[ií]deo)\b", re.IGNORECASE),
    "marriage": re.compile(r"\b(?:casad[ao]|marido|casamento)\b", re.IGNORECASE),
    "invitation": re.compile(r"\b(?:topa|aceita|vamos|que tal|caf[eé]|encontro)\b", re.IGNORECASE),
}
_THREAD_EQUIVALENTS = {"action", "initiative"}


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("episodic_memory") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    runtime = document.get("runtime_policy") or {}
    nested = runtime.get("episodic_memory") if isinstance(runtime, dict) else {}
    return dict(nested) if isinstance(nested, dict) else {}


def _load(facts: Mapping[str, str]) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(str(facts.get(_STORE_KEY, "") or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [dict(item) for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _save(facts: dict[str, str], memories: list[dict[str, Any]], maximum: int) -> None:
    facts[_STORE_KEY] = json.dumps(memories[-maximum:], ensure_ascii=False, separators=(",", ":"))


def _tags(text: str) -> list[str]:
    return [tag for tag, pattern in _TAG_PATTERNS.items() if pattern.search(text)]


def _significant(text: str, tags: list[str]) -> bool:
    return bool(tags or "?" in text or re.search(r"\b(?:lembra|promet|devendo|responde|explica)\w*\b", text, re.IGNORECASE))


def _status(text: str) -> str:
    if "?" in text or re.search(r"\b(?:promet|devendo|responde|explica)\w*\b", text, re.IGNORECASE):
        return "pending"
    return "reusable"


def capture_episode(
    document: Mapping[str, Any],
    facts: dict[str, str],
    user_text: str,
    *,
    source_beat_id: str,
) -> None:
    policy = _policy(document)
    if not policy:
        return
    text = " ".join(str(user_text or "").split()).strip()
    if not text:
        return

    memories = _load(facts)
    tags = _tags(text)
    recalled_id = str(facts.pop(_RECALLED_KEY, "") or "").strip()
    resolved_tags: set[str] = set()
    if recalled_id:
        for memory in memories:
            if str(memory.get("memory_id", "")) == recalled_id:
                memory["status"] = "resolved"
                memory["resolution"] = text[:280]
                resolved_tags = {str(tag) for tag in memory.get("tags", []) or []}
                break

    if recalled_id:
        carried = set(tags) - resolved_tags
        if resolved_tags.intersection(_THREAD_EQUIVALENTS):
            carried -= _THREAD_EQUIVALENTS
        if not carried:
            _save(facts, memories, int(policy.get("max_memories", 12) or 12))
            return

    if not _significant(text, tags):
        _save(facts, memories, int(policy.get("max_memories", 12) or 12))
        return

    sequence = int(facts.get(_SEQ_KEY, "0") or 0) + 1
    facts[_SEQ_KEY] = str(sequence)
    memories.append(
        {
            "memory_id": f"episode_{sequence:04d}",
            "summary": f'O usuário disse: "{text[:280]}"',
            "status": _status(text),
            "tags": tags or ["conversation"],
            "source_beat_id": str(source_beat_id or ""),
            "last_recalled_beat_id": "",
        }
    )
    _save(facts, memories, int(policy.get("max_memories", 12) or 12))


def _recall_tags(policy: Mapping[str, Any], beat_id: str) -> set[str]:
    for rule in policy.get("recall", []) or []:
        if not isinstance(rule, dict):
            continue
        prefixes = tuple(str(item) for item in rule.get("beat_prefixes", []) or [])
        beat_ids = {str(item) for item in rule.get("beat_ids", []) or []}
        if beat_id in beat_ids or any(beat_id.startswith(prefix) for prefix in prefixes):
            return {str(item) for item in rule.get("tags", []) or []}
    return set()


def recall_episode(
    document: Mapping[str, Any],
    facts: dict[str, str],
    *,
    beat_id: str,
) -> str:
    policy = _policy(document)
    wanted = _recall_tags(policy, str(beat_id or ""))
    if not wanted:
        return ""
    memories = _load(facts)
    candidates = [
        item
        for item in memories
        if item.get("status") in {"pending", "reusable"}
        and str(item.get("source_beat_id", "")) != beat_id
        and str(item.get("last_recalled_beat_id", "")) != beat_id
        and wanted.intersection({str(tag) for tag in item.get("tags", []) or []})
    ]
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (item.get("status") == "pending", item.get("memory_id", "")), reverse=True)
    selected = candidates[0]
    selected["last_recalled_beat_id"] = beat_id
    if selected.get("status") == "pending":
        selected["status"] = "recalled"
        facts[_RECALLED_KEY] = str(selected.get("memory_id", ""))
    _save(facts, memories, int(policy.get("max_memories", 12) or 12))
    return str(selected.get("summary", "")).strip()


__all__ = ["capture_episode", "recall_episode"]
