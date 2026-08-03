from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable

from services.editorial_engine import compile_transition_rules


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
    """Produz um contrato factual para qualquer beat sem inventar conteúdo.

    A derivação usa somente campos autorais já presentes no beat. Declarações
    explícitas ampliam e especializam a base; nunca são descartadas pelos
    padrões universais.
    """

    required_movement = str(source.get("required_movement", "") or "").strip()
    canonical_line = str(source.get("canonical_line", "") or "").strip()
    dramatic_direction = str(source.get("dramatic_direction", "") or "").strip()

    legacy_scope = _string_items(source.get("fact_scope") or constraints.get("fact_scope"))
    explicit_topics = _string_items(
        source.get("allowed_topics") or constraints.get("allowed_topics")
    )
    explicit_confirmed = _string_items(
        source.get("confirmed_facts") or constraints.get("confirmed_facts")
    )
    explicit_unknown = _string_items(
        source.get("unknown_facts") or constraints.get("unknown_facts")
    )

    derived_topics = [
        text
        for text in (required_movement, dramatic_direction)
        if text
    ]
    derived_confirmed = []
    if required_movement:
        derived_confirmed.append(f"movimento autorizado neste beat: {required_movement}")
    if canonical_line:
        derived_confirmed.append(
            f"conteúdo semântico autorizado pela linha canônica: {canonical_line}"
        )

    allowed_topics = _unique((*explicit_topics, *legacy_scope, *derived_topics))
    confirmed_facts = _unique((*explicit_confirmed, *derived_confirmed))
    unknown_facts = _unique((*explicit_unknown, *_DEFAULT_UNKNOWN_FACTS))
    return allowed_topics, confirmed_facts, unknown_facts


def compile_editorial_document(document: dict[str, Any]) -> dict[str, Any]:
    """Converte o documento editorial em uma cena executável sem alterar o conteúdo."""

    blocks = [deepcopy(item) for item in document.get("blocks", []) if isinstance(item, dict)]
    if not blocks:
        raise ValueError("O roteiro editorial não contém blocos.")
    blocks.sort(key=lambda item: int(item.get("order", 0) or 0))

    beats: list[dict[str, Any]] = []
    endings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for block in blocks:
        for source in sorted(
            [item for item in block.get("beats", []) if isinstance(item, dict)],
            key=lambda item: int(item.get("order", 0) or 0),
        ):
            beat_id = str(source.get("beat_id", "") or "").strip()
            if not beat_id or beat_id in seen_ids:
                raise ValueError(f"beat_id ausente ou duplicado: {beat_id!r}")
            seen_ids.add(beat_id)

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
                    }
                )
                continue

            canonical_line = str(source.get("canonical_line", ""))
            legacy_transitions = dict(source.get("allowed_transitions") or {})
            next_beat_id = str(source.get("next_beat_id", "") or "").strip()
            if next_beat_id and not legacy_transitions:
                legacy_transitions = {"engaged": next_beat_id}

            constraints = deepcopy(source.get("constraints") or {})
            allowed_topics, confirmed_facts, unknown_facts = _compiled_factual_contract(
                source,
                constraints,
            )
            fact_scope = deepcopy(source.get("fact_scope") or constraints.get("fact_scope") or [])

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
                    "terminal_transition": "",
                    "memory_writes": [str(item) for item in source.get("memory_writes", [])],
                    "max_questions": int(source.get("max_questions", 1) or 0),
                    "max_sentences": int(source.get("max_sentences", 1) or 1),
                    "skip_when_facts": deepcopy(source.get("skip_when_facts") or {}),
                    "response_boundary": str(source.get("response_boundary", "") or ""),
                    "fact_scope": fact_scope,
                    "allowed_topics": allowed_topics,
                    "confirmed_facts": confirmed_facts,
                    "unknown_facts": unknown_facts,
                    "factual_contract_mode": "explicit+derived",
                    "constraints": constraints,
                }
            )

    first_block = blocks[0]
    first_beat_id = str(first_block.get("entry_beat_id", "") or "").strip()
    if first_beat_id not in {item["beat_id"] for item in beats}:
        raise ValueError(f"Primeiro beat inexistente: {first_beat_id!r}")

    compiled = deepcopy(document)
    compiled["blocks"] = blocks
    compiled["scene"] = {
        "scene_id": str(first_block.get("block_id", "")),
        "location": str(first_block.get("title", "")),
        "objective": str(document.get("introduction", "")),
        "first_beat_id": first_beat_id,
        "beats": beats,
        "endings": endings,
    }
    return compiled
