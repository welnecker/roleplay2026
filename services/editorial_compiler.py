from __future__ import annotations

from copy import deepcopy
from typing import Any


def compile_editorial_document(document: dict[str, Any]) -> dict[str, Any]:
    """Converte o documento editorial em uma cena executável sem alterar o conteúdo.

    O documento com ``blocks`` continua sendo a única fonte. Esta função apenas
    adapta sua estrutura ao contrato genérico do motor ``PilotScript``.
    """

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
            transitions = dict(source.get("allowed_transitions") or {})
            next_beat_id = str(source.get("next_beat_id", "") or "").strip()
            if next_beat_id and not transitions:
                transitions = {"engaged": next_beat_id}

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
                    "on_user": transitions,
                    "terminal_transition": next_beat_id,
                    "memory_writes": [str(item) for item in source.get("memory_writes", [])],
                    "max_questions": int(source.get("max_questions", 1) or 0),
                    "max_sentences": int(source.get("max_sentences", 1) or 1),
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
