from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from services.narrative_context import NarrativeMemoryDefinition, memory_catalog


_RECALL_STATE_KEY = "_memory_recall_state_json"
_RECALL_TURN_KEY = "_memory_recall_turn"


@dataclass(frozen=True, slots=True)
class MemoryRecallCandidate:
    memory_id: str
    score: float
    matched_terms: tuple[str, ...]


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    value = relationship.get("recall_policy") or {}
    return dict(value) if isinstance(value, dict) else {}


def _tokens(text: str) -> set[str]:
    return {
        item.casefold()
        for item in re.findall(r"[^\W_]{3,}", str(text or ""), flags=re.UNICODE)
    }


def _recall_state(facts: Mapping[str, str]) -> dict[str, int]:
    raw = str(facts.get(_RECALL_STATE_KEY, "") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return {
        str(key): int(value)
        for key, value in parsed.items()
        if str(key).strip()
    } if isinstance(parsed, dict) else {}


def _memory_terms(memory: NarrativeMemoryDefinition, raw: Mapping[str, Any]) -> set[str]:
    """Retorna somente gatilhos editoriais realmente discriminantes.

    ``category`` e ``subject`` não entram automaticamente: valores genéricos como
    ``mary`` ou ``relationship`` causavam lembranças falsas em qualquer turno que
    apenas mencionasse a personagem ou o usuário.
    """

    declared = raw.get("recall_terms") or raw.get("triggers") or []
    values = [str(item) for item in declared] if isinstance(declared, list) else []
    values.extend(memory.tags)
    return _tokens(" ".join(values))


def select_contextual_memories(
    document: Mapping[str, Any],
    memory_ids: Iterable[str],
    facts: Mapping[str, str],
    context_text: str,
) -> tuple[list[str], dict[str, str]]:
    """Seleciona poucas memórias opcionais relevantes e atualiza cooldown interno."""

    policy = _policy(document)
    max_items = max(0, int(policy.get("max_memories_per_turn", 1) or 1))
    minimum_score = float(policy.get("minimum_context_score", 1.0) or 1.0)
    allow_background_fallback = bool(policy.get("allow_background_fallback", False))
    catalog = memory_catalog(dict(document))
    raw_catalog = document.get("memories") or {}
    raw_by_id = raw_catalog if isinstance(raw_catalog, dict) else {
        str(item.get("memory_id", "")): item
        for item in raw_catalog or []
        if isinstance(item, dict)
    }

    updated = {str(key): str(value) for key, value in dict(facts).items()}
    current_turn = int(updated.get(_RECALL_TURN_KEY, "0") or 0) + 1
    updated[_RECALL_TURN_KEY] = str(current_turn)
    last_recalled = _recall_state(updated)
    context_tokens = _tokens(context_text)
    candidates: list[MemoryRecallCandidate] = []

    for memory_id in dict.fromkeys(str(item).strip() for item in memory_ids if str(item).strip()):
        memory = catalog.get(memory_id)
        if memory is None or memory.status in {"forgotten", "superseded", "resolved"}:
            continue
        last_turn = int(last_recalled.get(memory_id, -10_000))
        if current_turn - last_turn <= memory.recall_cooldown_turns:
            continue
        raw = raw_by_id.get(memory_id) or {}
        terms = _memory_terms(memory, raw if isinstance(raw, dict) else {})
        matched = tuple(sorted(context_tokens.intersection(terms)))
        contextual_score = len(matched) * 2.0
        score = contextual_score + memory.recall_priority / 10.0
        if matched and score >= minimum_score:
            candidates.append(MemoryRecallCandidate(memory_id, score, matched))
        elif allow_background_fallback and memory.status == "background":
            candidates.append(MemoryRecallCandidate(memory_id, memory.recall_priority / 20.0, ()))

    candidates.sort(key=lambda item: (-item.score, item.memory_id))
    selected = [item.memory_id for item in candidates[:max_items]] if max_items else []
    for memory_id in selected:
        last_recalled[memory_id] = current_turn
    updated[_RECALL_STATE_KEY] = json.dumps(last_recalled, ensure_ascii=False, sort_keys=True)
    updated["_recalled_memory_ids"] = ",".join(selected)
    return selected, updated


def render_memory_recall_guidance(selected_ids: Iterable[str]) -> str:
    selected = [str(item).strip() for item in selected_ids if str(item).strip()]
    if not selected:
        return ""
    return (
        "USO NATURAL DA MEMÓRIA:\n"
        "- Use no máximo uma referência breve às memórias selecionadas, somente se couber naturalmente na reação.\n"
        "- Não diga que está lembrando, não cite IDs e não recite a ficha da relação.\n"
        "- A memória deve mudar a interpretação ou a escolha de palavras, não interromper o movimento atual.\n"
        "- Não repita a mesma lembrança em turnos consecutivos."
    )


__all__ = ["MemoryRecallCandidate", "render_memory_recall_guidance", "select_contextual_memories"]
