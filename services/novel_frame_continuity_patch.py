from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from services import novel_frame_patch

_installed = False
_original_compile_novel_frame_story = None
_original_build_frame_prompt = None


def _items(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def continuity_contract_from_document(document: dict[str, Any]) -> dict[str, object]:
    """Extrai apenas fatos canônicos necessários para impedir deriva entre quadros."""

    core = document.get("character_core") or {}
    if not isinstance(core, dict):
        core = {}
    contract: dict[str, object] = {}
    summary = str(core.get("summary", "") or "").strip()
    if summary:
        contract["character_summary"] = summary
    runtime_rules = _items(document.get("runtime_rules"))
    if runtime_rules:
        contract["runtime_rules"] = runtime_rules
    return contract


def _compile_with_continuity(
    base_document: dict[str, Any],
    rows,
    *,
    script_version: str,
) -> dict[str, Any]:
    assert _original_compile_novel_frame_story is not None
    document = _original_compile_novel_frame_story(
        base_document,
        rows,
        script_version=script_version,
    )
    contract = continuity_contract_from_document(base_document)
    if not contract:
        return document

    enriched = deepcopy(document)
    prefix = novel_frame_patch._FRAME_PREFIX
    for block in enriched.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        for beat in block.get("beats", []) or []:
            if not isinstance(beat, dict):
                continue
            movement = str(beat.get("required_movement", "") or "")
            if not movement.startswith(prefix):
                continue
            try:
                frame = json.loads(movement[len(prefix) :])
            except json.JSONDecodeError:
                continue
            if not isinstance(frame, dict):
                continue
            frame["continuity_contract"] = deepcopy(contract)
            beat["required_movement"] = prefix + json.dumps(
                frame,
                ensure_ascii=False,
                separators=(",", ":"),
            )
    return enriched


def _build_frame_prompt_with_continuity(
    *,
    character_name: str,
    user_name: str,
    movement: Any,
) -> str:
    assert _original_build_frame_prompt is not None
    prompt = _original_build_frame_prompt(
        character_name=character_name,
        user_name=user_name,
        movement=movement,
    )
    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict):
        return prompt
    contract = frame.get("continuity_contract")
    if not isinstance(contract, dict) or not contract:
        return prompt

    canonical = json.dumps(contract, ensure_ascii=False, indent=2)
    guard = f"""

CONTRATO CANÔNICO DE IDENTIDADE E RELAÇÕES — PREVALECE SOBRE O HISTÓRICO:
{canonical}

- O contrato acima é a autoridade para identidade, relações e nomes dos personagens.
- O histórico serve apenas para continuidade dos acontecimentos da mesma versão; ele nunca pode renomear personagens nem contrariar o contrato canônico.
- Nomes próprios presentes apenas no histórico, mas ausentes do roteiro atual e do contrato canônico, são resíduos não autoritativos e devem ser ignorados.
- Se um personagem for identificado no roteiro apenas por função ou papel, como professor, médico, motorista ou vizinha, mantenha esse papel sem inventar nem recuperar um nome próprio.
- Nunca transforme um personagem terceiro no protagonista autenticado, nem o protagonista em um terceiro personagem.
""".rstrip()
    return prompt + guard


def install() -> None:
    global _installed
    global _original_compile_novel_frame_story
    global _original_build_frame_prompt
    if _installed:
        return
    _original_compile_novel_frame_story = novel_frame_patch.compile_novel_frame_story
    _original_build_frame_prompt = novel_frame_patch.build_frame_prompt
    novel_frame_patch.compile_novel_frame_story = _compile_with_continuity
    novel_frame_patch.build_frame_prompt = _build_frame_prompt_with_continuity
    _installed = True


__all__ = ["continuity_contract_from_document", "install"]
