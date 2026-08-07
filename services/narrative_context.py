from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True, slots=True)
class NarrativeMemoryDefinition:
    memory_id: str
    category: str
    importance: int
    summary: str


def _items(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _core_section(lines: list[str], title: str, values: Any) -> None:
    items = _items(values)
    if not items:
        return
    lines.append(f"{title}:")
    lines.extend(f"- {item}" for item in items)


def render_character_core(document: dict[str, Any]) -> str:
    """Renderiza um único núcleo autoritativo para beats, pontes e pátios.

    Cards novos podem declarar ``character_core`` no documento editorial. Quando
    presente, esse bloco substitui a ficha fragmentada no prompt e passa a ser a
    única referência estável de interpretação da personagem. Cards antigos
    continuam usando ``physical_profile``, ``psychological_profile`` e
    ``speech_style`` por compatibilidade.
    """

    core = document.get("character_core") or {}
    if not isinstance(core, Mapping) or not core:
        return ""

    character = document.get("character") or {}
    name = str(character.get("name", "Mary") or "Mary")
    age = int(character.get("age", 0) or 0)
    summary = str(core.get("summary", "") or "").strip()

    lines = [f"NÚCLEO VIVO E AUTORITATIVO DE {name.upper()}:"]
    if age > 0:
        lines.append(f"- idade: {age} anos")
    if summary:
        lines.append(f"- essência: {summary}")

    _core_section(lines, "APARÊNCIA FÍSICA", core.get("physical"))
    _core_section(lines, "PSICOLOGIA ESTÁVEL", core.get("psychological"))
    _core_section(lines, "REGRAS DO PENSAMENTO INTERNO", core.get("thought_rules"))
    _core_section(lines, "COMO ESTE NÚCLEO ORIENTA OS BEATS", core.get("beat_guidance"))
    _core_section(lines, "COMO ESTE NÚCLEO ORIENTA AS PONTES", core.get("bridge_guidance"))
    lines.extend(
        (
            "REGRA DE CONTINUIDADE:",
            "- Beats e pontes são caminhos diferentes do mesmo personagem; nunca troque a psicologia de Mary entre eles.",
            "- O roteiro decide o acontecimento e a progressão; este núcleo decide a percepção, o desejo, o humor, o disfarce e a iniciativa de Mary.",
        )
    )
    return "\n".join(lines)


def character_context(document: dict[str, Any]) -> str:
    core = render_character_core(document)
    if core:
        return core

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
    return character_context(document) + "\n\n" + render_active_memories(document, memory_ids, facts)


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


def _safe_format(template: str, variables: dict[str, str]) -> str:
    class SafeDict(dict[str, str]):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    return template.format_map(SafeDict(variables)).strip()


__all__ = [
    "NarrativeMemoryDefinition",
    "build_narrative_context",
    "character_context",
    "memory_catalog",
    "render_active_memories",
    "render_character_core",
    "validate_memory_references",
    "validate_terminal_yards",
]
