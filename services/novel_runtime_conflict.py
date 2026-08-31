from __future__ import annotations


def persisted_movement_at_sequence(
    messages: list[dict[str, object]],
    *,
    sequence: int,
    target_id: str,
) -> dict[str, object] | None:
    """Retorna somente o movimento persistido que resolve a mesma operação."""

    expected_sequence = max(1, int(sequence or 1))
    expected_target = str(target_id or "").strip()
    for item in messages:
        if str(item.get("role", "")) != "assistant":
            continue
        if int(item.get("sequence", 0) or 0) != expected_sequence:
            continue
        persisted_target = str(
            item.get("editorial_node") or item.get("beat_id") or ""
        ).strip()
        if persisted_target == expected_target:
            return item
    return None
