from __future__ import annotations

import unicodedata
from typing import Any

from services import novel_frame_patch
from services.novel_frame_reveal import frame_id, normalize_frame_markers


class FrameOutputContractError(ValueError):
    pass


def _plain(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold().strip()


def _signature(kind: object, actor: object) -> tuple[str, str]:
    return _plain(kind), _plain(actor)


def enforce_frame_output_contract(movement: Any, content: str) -> str:
    """Garante correspondência 1:1 entre entries autorais e resposta persistida."""

    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict):
        return str(content or "").strip()

    source = normalize_frame_markers(str(content or ""))
    expected_frame_id = str(frame.get("frame_id", "") or "").strip()
    if frame_id(source) != expected_frame_id:
        raise FrameOutputContractError("O modelo devolveu um quadro diferente do roteiro.")

    parts = novel_frame_patch._parse_output(source)
    if parts is None:
        raise FrameOutputContractError("O modelo não respeitou o formato do quadro V2.")

    expected_entries = [
        entry for entry in frame.get("entries", []) or [] if isinstance(entry, dict)
    ]
    expected = [
        _signature(entry.get("kind", ""), entry.get("actor", ""))
        for entry in expected_entries
    ]

    description = next(
        (body for kind, _actor, _name, body in parts if kind == "descricao" and body),
        "",
    )
    candidates = [
        (kind, actor, visible_name, body)
        for kind, actor, visible_name, body in parts
        if kind in {"fala", "pensamento"} and body
    ]

    selected: list[tuple[str, str, str, str]] = []
    expected_index = 0
    for candidate in candidates:
        signature = _signature(candidate[0], candidate[1])
        if expected_index < len(expected) and signature == expected[expected_index]:
            selected.append(candidate)
            expected_index += 1
            continue
        # Só é seguro remover uma entry que não poderia ocupar nenhuma posição
        # autoral restante. Duplicações/trocas potencialmente ambíguas são rejeitadas.
        if signature not in expected[expected_index:]:
            continue
        raise FrameOutputContractError(
            "O modelo alterou a ordem, omitiu ou duplicou uma entry do roteiro."
        )

    if expected_index != len(expected):
        raise FrameOutputContractError("O modelo omitiu uma ou mais entries do roteiro.")

    output = [f"[QUADRO {expected_frame_id}]"]
    authored_description = str(frame.get("description", "") or "").strip()
    if authored_description:
        if not description:
            raise FrameOutputContractError("O modelo omitiu a descrição do quadro.")
        output.extend(("[DESCRIÇÃO]", description))
    for kind, actor, visible_name, body in selected:
        label = "PENSAMENTO" if kind == "pensamento" else "FALA"
        actor_spec = actor + (f"|{visible_name}" if visible_name else "")
        output.extend((f"[{label} {actor_spec}]", body))
    output.append("[/QUADRO]")
    return "\n".join(output)


__all__ = ["FrameOutputContractError", "enforce_frame_output_contract"]
