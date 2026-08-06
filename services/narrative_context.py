from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


_MEMORY_STATUSES = {"active", "background", "resolved", "superseded", "forgotten", "sensitive"}


@dataclass(frozen=True, slots=True)
class NarrativeMemoryDefinition:
    """Memória declarada pelo card, independente de personagem ou história."""

    memory_id: str
    category: str
    importance: int
    summary: str
    subject: str = "relationship"
    emotional_weight: int = 5
    relationship_relevance: int = 5
    confidence: float = 1.0
    status: str = "active"
    sensitivity: str = "normal"
    recall_cooldown_turns: int = 0
    tags: tuple[str, ...] = ()

    @property
    def recall_priority(self) -> float:
        """Prioridade estável; relevância contextual poderá ser somada pelo runtime futuro."""

        return (
            self.importance * 0.40
            + self.emotional_weight * 0.30
            + self.relationship_relevance * 0.30
        ) * self.confidence


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


def relational_profile_context(document: dict[str, Any]) -> str:
    """Renderiza o eixo relacional configurado pelo card, sem conhecer Mary."""

    raw = document.get("relationship_memory") or {}
    if not isinstance(raw, dict) or not raw:
        return ""

    title = str(raw.get("title", "EIXO RELACIONAL DA HISTÓRIA") or "EIXO RELACIONAL DA HISTÓRIA")
    premise = str(raw.get("premise", "") or "").strip()
    awakening = str(raw.get("awakening", "") or "").strip()
    character_view = str(raw.get("character_view_of_user", "") or "").strip()
    motivations = _items(raw.get("motivations"))
    tensions = _items(raw.get("tensions"))
    guardrails = _items(raw.get("interpretation_rules"))

    lines: list[str] = []
    if premise:
        lines.append(f"- Situação de origem: {premise}")
    if awakening:
        lines.append(f"- Transformação em curso: {awakening}")
    if character_view:
        lines.append(f"- Como a personagem percebe o usuário: {character_view}")
    lines.extend(f"- Motivação: {item}" for item in motivations)
    lines.extend(f"- Tensão interna: {item}" for item in tensions)
    lines.extend(f"- Regra de interpretação: {item}" for item in guardrails)
    return f"{title}:\n" + "\n".join(lines) if lines else ""


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
        raw_status = str(value.get("status", "active") or "active").strip().casefold()
        status = raw_status if raw_status in _MEMORY_STATUSES else "active"
        definitions[memory_id] = NarrativeMemoryDefinition(
            memory_id=memory_id,
            category=str(value.get("category", "event") or "event"),
            importance=_score(value.get("importance", 5)),
            summary=summary,
            subject=str(value.get("subject", "relationship") or "relationship"),
            emotional_weight=_score(value.get("emotional_weight", 5)),
            relationship_relevance=_score(value.get("relationship_relevance", 5)),
            confidence=_confidence(value.get("confidence", 1.0)),
            status=status,
            sensitivity=str(value.get("sensitivity", "normal") or "normal"),
            recall_cooldown_turns=max(0, int(value.get("recall_cooldown_turns", 0) or 0)),
            tags=tuple(_items(value.get("tags"))),
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
    selected = [
        catalog[memory_id]
        for memory_id in memory_ids
        if memory_id in catalog and catalog[memory_id].status not in {"forgotten", "superseded"}
    ]
    selected.sort(key=lambda item: (-item.recall_priority, item.memory_id))
    selected = selected[: max(1, int(max_items))]
    if not selected:
        return "MEMÓRIAS DA RELAÇÃO:\n- Nenhuma memória narrativa consolidada ainda."

    variables = {str(key): str(value) for key, value in dict(facts or {}).items()}
    variables.setdefault("user_name", "o usuário")
    lines = []
    for item in selected:
        summary = _safe_format(item.summary, variables)
        metadata = (
            f"categoria={item.category}; sujeito={item.subject}; "
            f"peso emocional={item.emotional_weight}/10; "
            f"relevância relacional={item.relationship_relevance}/10; estado={item.status}"
        )
        lines.append(f"- {summary} ({metadata})")
    return "MEMÓRIAS DA RELAÇÃO:\n" + "\n".join(lines)


def build_narrative_context(
    document: dict[str, Any],
    memory_ids: Iterable[str],
    facts: dict[str, str] | None = None,
) -> str:
    sections = [
        character_context(document),
        relational_profile_context(document),
        render_active_memories(document, memory_ids, facts),
    ]
    return "\n\n".join(section for section in sections if section.strip())


def validate_memory_references(document: dict[str, Any]) -> None:
    known = set(memory_catalog(document))
    for block in document.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []) or []:
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("beat_id", ""))
            for memory_id in beat.get("memory_writes", []) or []:
                if str(memory_id) not in known:
                    raise ValueError(f"Memória inexistente no beat {beat_id}: {memory_id}")


def validate_terminal_yards(document: dict[str, Any]) -> None:
    """Garante desaceleração real: dois movimentos e saída exclusivamente terminal."""

    ending_ids = {
        str(beat.get("beat_id", ""))
        for block in document.get("blocks", []) or []
        if isinstance(block, dict)
        for beat in block.get("beats", []) or []
        if isinstance(beat, dict) and str(beat.get("type", "dialogue")) == "ending"
    }
    for block in document.get("blocks", []) or []:
        if not isinstance(block, dict) or str(block.get("block_type", "")) != "terminal_yard":
            continue
        block_id = str(block.get("block_id", ""))
        beats = [
            beat
            for beat in block.get("beats", []) or []
            if isinstance(beat, dict) and str(beat.get("type", "dialogue")) != "ending"
        ]
        if len(beats) < 2:
            raise ValueError(f"Pátio terminal {block_id} precisa de pelo menos dois movimentos.")
        if int(block.get("min_user_turns", 0) or 0) < 2:
            raise ValueError(f"Pátio terminal {block_id} precisa de min_user_turns >= 2.")
        yard_ids = {str(beat.get("beat_id", "")) for beat in beats}
        for index, beat in enumerate(beats):
            transitions = dict(beat.get("allowed_transitions") or {})
            ordinary_targets = {
                str(target)
                for kind, target in transitions.items()
                if kind not in {"mocking", "hostile"} and str(target).strip()
            }
            if index < len(beats) - 1:
                if not ordinary_targets or not ordinary_targets.issubset(yard_ids):
                    raise ValueError(f"Pátio {block_id} saiu antes da despedida final.")
            elif not ordinary_targets or not ordinary_targets.issubset(ending_ids):
                raise ValueError(f"Último movimento do pátio {block_id} deve apontar para ending.")


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _score(value: Any) -> int:
    return max(0, min(10, int(value or 0)))


def _confidence(value: Any) -> float:
    return max(0.0, min(1.0, float(value if value is not None else 1.0)))


def _safe_format(template: str, variables: dict[str, str]) -> str:
    class SafeDict(dict[str, str]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(SafeDict(variables)).strip()
