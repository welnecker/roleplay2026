from __future__ import annotations

import re
from collections.abc import Iterable


def next_image_number(
    prefix: str,
    start: int,
    *,
    image_source_ids: Iterable[object] = (),
    mapped_image_ids: Iterable[object] = (),
    binding_image_ids: Iterable[object] = (),
) -> int:
    """Calcula o próximo número usando todos os IDs persistidos no projeto."""

    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)\.webp$", re.IGNORECASE)
    used: list[int] = []
    for value in (*image_source_ids, *mapped_image_ids, *binding_image_ids):
        match = pattern.match(str(value or "").strip())
        if match:
            used.append(int(match.group(1)))
    return max([int(start) - 1, *used]) + 1


__all__ = ["next_image_number"]
