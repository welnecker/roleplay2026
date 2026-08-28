from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from services import novel_frame_patch
from services.novel_v2_adapter import movement_from_script, next_movement_id

_FRAME_PREFIX = "NOVEL_FRAME_V2\n"
_AUTHORING_SOURCE = "spreadsheet_novel_frame_v2"


def is_frame_script(script: Any) -> bool:
    raw = getattr(script, "raw", {}) or {}
    return str(raw.get("authoring_source", "") or "").strip() == _AUTHORING_SOURCE


def build_runtime_prompt(*, character_name: str, user_name: str, movement: Any) -> str:
    """Seleciona o prompt correto sem depender da ordem de patches do frontend."""

    if novel_frame_patch._frame_from_movement(movement) is not None:
        return novel_frame_patch.build_frame_prompt(
            character_name=character_name,
            user_name=user_name,
            movement=movement,
        )

    from services.novel_v2_adapter import build_novel_prompt

    return build_novel_prompt(
        character_name=character_name,
        user_name=user_name,
        movement=movement,
    )


def first_frame_movement(script: Any):
    """Resolve o primeiro quadro e garante que sua DESCRIÇÃO esteja no payload.

    A versão anterior promovia a primeira descrição a scene_introduction e a
    removia do payload do encontro_001. Para a apresentação uniforme, a abertura
    passa a ser o quadro completo; por isso recompomos a descrição antes de gerar.
    """

    target_id = next_movement_id(script, "")
    if not target_id:
        raise ValueError("Roteiro V2 não possui primeiro quadro.")
    movement = movement_from_script(script, target_id)
    if not is_frame_script(script):
        return target_id, movement

    instruction = str(getattr(movement, "instruction", "") or "")
    if not instruction.startswith(_FRAME_PREFIX):
        return target_id, movement

    payload = json.loads(instruction[len(_FRAME_PREFIX):])
    if not isinstance(payload, dict):
        raise ValueError("Payload do primeiro quadro V2 é inválido.")

    if not str(payload.get("description", "") or "").strip():
        scene = getattr(script, "scene", {}) or {}
        description = str(scene.get("introduction", "") or "").strip()
        if not description:
            raise ValueError("Primeiro quadro V2 não possui [DESCRIÇÃO].")
        payload["description"] = description

    return target_id, replace(
        movement,
        instruction=_FRAME_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )


__all__ = ["build_runtime_prompt", "first_frame_movement", "is_frame_script"]
