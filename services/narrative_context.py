from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class NarrativeMemoryDefinition:
    memory_id: str
    category: str
    importance: int
    summary: str


def character_context(document: dict[str, Any]) -> str:
    character = document.get("character") or {}
    name = str(character.get("name", "Mary") or "Mary")
    age = int(character.get("age", 0) or 0)
    physical = _items(character.get("physical_profile"))
    psychological = _items(character.get("psychological_profile"))
    speech = _items(character.get("speech_style"))

    identity_parts = [name]
    if age > 0:
        identity_parts.append(f"{age} anos")
    if physical:
        identity_parts.append(", ".join(physical))

    sections = [f"IDENTIDADE ESTÁVEL DE {name.upper()}:\n- " + "; ".join(identity_parts)]
    if psychological:
        sections.append("PERSONALIDADE ESTÁVEL:\n- " + "\n- ".join(psychological))
    if speech:
        sections.append("ESTILO DE FALA:\n- " + "\n- ".join(speech))
    return "\n\n".join(sections)


def memory_catalog(document: dict[str, Any]) -> dict[str, NarrativeMemoryDefinition]:
    raw = document.get("memories") or {}
    definitions: dict[str, NarrativeMemoryDefinition] = {}

    if isinstance(raw, dict):
        iterable = ((str(memory_id), value) for memory_id, value in raw.items())
    elif isinstance(raw, list):
        iterable = (
            (str(item.get("memory_id", "")), item)
            for item in raw
            if isinstance(item, dict)
        )
    else:
        iterable = ()

    for memory_id, value in iterable:
        if not memory_id or not isinstance(value, dict):
            continue
        summary = str(value.get("summary") or value.get("memory_text") or "").strip()
        if not summary:
            continue
        definitions[memory_id] = NarrativeMemoryDefinition(
            memory_id=memory_id,
            category=str(value.get("category", "event") or "event"),
            importance=max(0, min(10, int(value.get("importance", 5) or 5))),
            summary=summary,
        )
    return definitions


def render_active_memories(
    document: dict[str, Any],
    memory_ids: Iterable[str],
    facts: dict[str, str] | None = None,
    *,
    max_items: int = 12,
) -> str:
    catalog = memory_catalog(document)
    selected = [catalog[memory_id] for memory_id in memory_ids if memory_id in catalog]
    selected.sort(key=lambda item: (-item.importance, item.memory_id))
    selected = selected[: max(1, int(max_items))]
    if not selected:
        return "MEMÓRIAS DA RELAÇÃO:\n- Nenhuma memória narrativa consolidada ainda."

    variables = {str(key): str(value) for key, value in dict(facts or {}).items()}
    variables.setdefault("user_name", "o usuário")
    lines = [f"- {_safe_format(item.summary, variables)}" for item in selected]
    return "MEMÓRIAS DA RELAÇÃO:\n" + "\n".join(lines)


def build_narrative_context(
    document: dict[str, Any],
    memory_ids: Iterable[str],
    facts: dict[str, str] | None = None,
) -> str:
    return (
        character_context(document)
        + "\n\n"
        + render_active_memories(document, memory_ids, facts)
    )


def validate_memory_references(document: dict[str, Any]) -> None:
    catalog = memory_catalog(document)
    known = set(catalog)
    for block in document.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []) or []:
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            for memory_id in beat.get("memory_writes", []) or []:
                if str(memory_id) not in known:
                    raise ValueError(
                        f"Memória inexistente no beat {beat_id}: {memory_id}"
                    )


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _safe_format(template: str, variables: dict[str, str]) -> str:
    class SafeDict(dict[str, str]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(SafeDict(variables)).strip()
