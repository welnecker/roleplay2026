from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from services.editorial_engine import compile_transition_rules
from services.editorial_interaction_context import (
    merge_interaction_context,
    validate_interaction_context,
)


_DEFAULT_UNKNOWN_FACTS = (
    "ações, decisões, falas, pensamentos e intenções do usuário que não tenham sido declarados",
    "localização exata, distância ou deslocamento que não tenham sido declarados",
    "quantidade, medida, peso, conteúdo ou composição que não tenham sido declarados",
    "roupas, objetos, aparência ou condição física que não tenham sido declarados",
    "causa, risco, esforço, urgência ou consequência que não tenham sido declarados",
    "acontecimentos, decisões ou resultados pertencentes a beats futuros",
)


def _string_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))


def _compiled_factual_contract(
    source: dict[str, Any],
    constraints: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    required_movement = str(source.get("required_movement", "") or "").strip()
    canonical_line = str(source.get("canonical_line", "") or "").strip()
    dramatic_direction = str(source.get("dramatic_direction", "") or "").strip()
    legacy_scope = _string_items(source.get("fact_scope") or constraints.get("fact_scope"))
    explicit_topics = _string_items(source.get("allowed_topics") or constraints.get("allowed_topics"))
    explicit_confirmed = _string_items(source.get("confirmed_facts") or constraints.get("confirmed_facts"))
    explicit_unknown = _string_items(source.get("unknown_facts") or constraints.get("unknown_facts"))
    derived_topics = [text for text in (required_movement, dramatic_direction) if text]
    derived_confirmed = []
    if required_movement:
        derived_confirmed.append(f"movimento autorizado neste beat: {required_movement}")
    if canonical_line:
        derived_confirmed.append(f"conteúdo semântico autorizado pela linha canônica: {canonical_line}")
    return (
        _unique((*explicit_topics, *legacy_scope, *derived_topics)),
        _unique((*explicit_confirmed, *derived_confirmed)),
        _unique((*explicit_unknown, *_DEFAULT_UNKNOWN_FACTS)),
    )


def _ordinary_targets(source: dict[str, Any]) -> set[str]:
    transitions = dict(source.get("allowed_transitions") or {})
    next_beat_id = str(source.get("next_beat_id", "") or "").strip()
    if next_beat_id and not transitions:
        transitions = {"engaged": next_beat_id}
    return {
        str(target).strip()
        for kind, target in transitions.items()
        if kind not in {"mocking", "hostile"} and str(target).strip()
    }


def compile_editorial_document(document: dict[str, Any]) -> dict[str, Any]:
    """Converte o documento em grafo executável preservando blocos e contexto."""

    root_interaction_context = deepcopy(document.get("interaction_context") or {})
    validate_interaction_context(root_interaction_context, location="interaction_context do card")
    blocks = [deepcopy(item) for item in document.get("blocks", []) if isinstance(item, dict)]
    if not blocks:
        raise ValueError("O roteiro editorial não contém blocos.")
    blocks.sort(key=lambda item: int(item.get("order", 0) or 0))

    ending_ids = {
        str(source.get("beat_id", "") or "").strip()
        for block in blocks
        for source in block.get("beats", []) or []
        if isinstance(source, dict) and str(source.get("type", "dialogue")) == "ending"
    }
    beats: list[dict[str, Any]] = []
    endings: list[dict[str, Any]] = []
    terminal_yards: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()

    for block in blocks:
        block_id = str(block.get("block_id", "") or "").strip()
        block_type = str(block.get("block_type", "canonical") or "canonical").strip()
        block_declared_context = deepcopy(block.get("interaction_context") or {})
        validate_interaction_context(
            block_declared_context,
            location=f"interaction_context do bloco {block_id}",
        )
        block_interaction_context = merge_interaction_context(
            root_interaction_context,
            block_declared_context,
        )
        block["compiled_interaction_context"] = deepcopy(block_interaction_context)
        ordered_sources = sorted(
            [item for item in block.get("beats", []) if isinstance(item, dict)],
            key=lambda item: int(item.get("order", 0) or 0),
        )
        dialogue_sources = [item for item in ordered_sources if str(item.get("type", "dialogue")) != "ending"]
        dialogue_ids = [str(item.get("beat_id", "") or "").strip() for item in dialogue_sources]

        if block_type == "terminal_yard":
            yard_endings = sorted(
                target
                for source in dialogue_sources
                for target in _ordinary_targets(source)
                if target in ending_ids
            )
            terminal_yards[block_id] = {
                "yard_id": block_id,
                "entry_beat_id": str(block.get("entry_beat_id", "") or "").strip(),
                "beat_ids": dialogue_ids,
                "min_user_turns": int(block.get("min_user_turns", 0) or 0),
                "max_user_turns": int(block.get("max_user_turns", 0) or 0),
                "ending_ids": list(dict.fromkeys(yard_endings)),
                "rules": [str(item) for item in block.get("rules", []) or []],
            }

        for position, source in enumerate(ordered_sources, start=1):
            beat_id = str(source.get("beat_id", "") or "").strip()
            if not beat_id or beat_id in seen_ids:
                raise ValueError(f"beat_id ausente ou duplicado: {beat_id!r}")
            seen_ids.add(beat_id)
            beat_declared_context = deepcopy(source.get("interaction_context") or {})
            validate_interaction_context(
                beat_declared_context,
                location=f"interaction_context do beat {beat_id}",
            )
            effective_interaction_context = merge_interaction_context(
                block_interaction_context,
                beat_declared_context,
            )

            if str(source.get("type", "dialogue")) == "ending":
                ending_data = dict(source.get("ending") or {})
                endings.append(
                    {
                        "ending_id": beat_id,
                        "run_status": str(ending_data.get("run_status", "completed")),
                        "ending_code": str(ending_data.get("ending_code", beat_id)),
                        "visible_delivery": {
                            "kind": "dialogue",
                            "delivery": "guided",
                            "text": str(source.get("canonical_line", "")),
                        },
                        "memory_writes": [str(item) for item in source.get("memory_writes", [])],
                        "block_id": block_id,
                        "block_type": block_type,
                        "interaction_context": effective_interaction_context,
                    }
                )
                continue

            canonical_line = str(source.get("canonical_line", ""))
            legacy_transitions = dict(source.get("allowed_transitions") or {})
            next_beat_id = str(source.get("next_beat_id", "") or "").strip()
            if next_beat_id and not legacy_transitions:
                legacy_transitions = {"engaged": next_beat_id}
            constraints = deepcopy(source.get("constraints") or {})
            allowed_topics, confirmed_facts, unknown_facts = _compiled_factual_contract(source, constraints)
            fact_scope = deepcopy(source.get("fact_scope") or constraints.get("fact_scope") or [])
            resolved_topics_on_exit = _string_items(
                source.get("resolve_topics_on_exit")
                or source.get("resolve_topic_on_exit")
            )

            beats.append(
                {
                    "beat_id": beat_id,
                    "objective": str(source.get("required_movement", "")),
                    "units": [
                        {
                            "unit_id": f"{beat_id}_canonical",
                            "kind": "dialogue",
                            "delivery": "anchored",
                            "anchor": canonical_line,
                            "instruction": str(source.get("dramatic_direction", "")),
                        },
                        {"unit_id": f"{beat_id}_wait", "kind": "wait_user"},
                    ],
                    "on_user": legacy_transitions,
                    "transition_rules": compile_transition_rules(source),
                    "intent_classifiers": deepcopy(source.get("intent_classifiers") or []),
                    "terminal_transition": str(source.get("terminal_transition", "") or "").strip(),
                    "memory_writes": [str(item) for item in source.get("memory_writes", [])],
                    "max_questions": int(source.get("max_questions", 1) or 0),
                    "max_sentences": int(source.get("max_sentences", 1) or 1),
                    "skip_when_facts": deepcopy(source.get("skip_when_facts") or {}),
                    "response_boundary": str(source.get("response_boundary", "") or ""),
                    "topic_id": str(source.get("topic_id", "") or "").strip(),
                    "resolve_topics_on_exit": resolved_topics_on_exit,
                    "fact_scope": fact_scope,
                    "allowed_topics": allowed_topics,
                    "confirmed_facts": confirmed_facts,
                    "unknown_facts": unknown_facts,
                    "factual_contract_mode": "explicit+derived",
                    "constraints": constraints,
                    "profile_delivery": deepcopy(source.get("profile_delivery") or {}),
                    "authored_thought": str(source.get("authored_thought", "") or ""),
                    "exact_speech": str(source.get("exact_speech", "") or ""),
                    "has_authored_bridge": bool(source.get("has_authored_bridge", False)),
                    "block_id": block_id,
                    "block_type": block_type,
                    "position_in_block": position,
                    "block_size": len(dialogue_sources),
                    "terminal_yard_id": block_id if block_type == "terminal_yard" else "",
                    "yard_min_user_turns": int(block.get("min_user_turns", 0) or 0),
                    "yard_max_user_turns": int(block.get("max_user_turns", 0) or 0),
                    "interaction_context": effective_interaction_context,
                }
            )

    beat_ids = {item["beat_id"] for item in beats}
    first_block = blocks[0]
    first_beat_id = str(first_block.get("entry_beat_id", "") or "").strip()
    if first_beat_id not in beat_ids:
        if str(document.get("authoring_source", "")) != "spreadsheet" or not beats:
            raise ValueError(f"Primeiro beat inexistente: {first_beat_id!r}")
        first_beat = beats[0]
        first_beat_id = str(first_beat["beat_id"])
        first_block = next(
            (
                block
                for block in blocks
                if str(block.get("block_id", "")) == str(first_beat.get("block_id", ""))
            ),
            blocks[0],
        )
        first_block["entry_beat_id"] = first_beat_id
        blocks = [first_block, *(block for block in blocks if block is not first_block)]
        for block_order, block in enumerate(blocks, start=1):
            block["order"] = block_order
    compiled = deepcopy(document)
    compiled["blocks"] = blocks
    compiled["scene"] = {
        "scene_id": str(first_block.get("block_id", "")),
        "location": str(first_block.get("title", "")),
        "objective": str(document.get("introduction", "")),
        "first_beat_id": first_beat_id,
        "beats": beats,
        "endings": endings,
        "terminal_yards": terminal_yards,
    }
    return compiled
