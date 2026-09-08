from __future__ import annotations

"""Transforma [FIM_HISTORIA] com texto em uma despedida visual determinística.

A linha terminal continua vindo de ROTEIROS, mas não passa pelo modelo. Quando
existe texto depois da tag, compilamos um quadro V2 próprio, com a imagem autoral
da mesma linha. O FletRunService monta a saída canônica diretamente, persiste a
interação e conclui a run. Marcadores antigos sem texto preservam o comportamento
legado de apenas marcar o quadro anterior como terminal.
"""

import json
import re
from functools import wraps
from typing import Any

import services.editorial_content as editorial_content
from flet_api.runs import FletRunService
from services import novel_frame_patch
from services.immersive_onboarding import persistent_profile_payload, recover_persistent_profile
from services.novel_frame_runtime_support import first_frame_movement
from services.novel_v2_adapter import movement_from_script
from services.runtime_persistence import persist_assistant_message


_INSTALLED = False
_MARKER = re.compile(r"^\s*\[\s*fim_historia\s*\]\s*(?P<body>.*)$", re.IGNORECASE | re.DOTALL)
_TERMINAL_KIND = "story_end"


def _active_sorted(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active = [
        dict(row)
        for row in rows
        if str(row.get("status", "active") or "active").strip().casefold() == "active"
    ]
    active.sort(key=lambda row: (int(row.get("order", 0) or 0), str(row.get("line_id", ""))))
    return active


def _story_end_rows(rows: list[dict[str, Any]]) -> list[tuple[int, dict[str, Any], re.Match[str]]]:
    found: list[tuple[int, dict[str, Any], re.Match[str]]] = []
    for index, row in enumerate(_active_sorted(rows)):
        match = _MARKER.fullmatch(str(row.get("instruction", "") or ""))
        if match is not None:
            found.append((index, row, match))
    return found


def _append_terminal_card(
    document: dict[str, Any],
    *,
    row: dict[str, Any],
    body: str,
) -> dict[str, Any]:
    blocks = [item for item in document.get("blocks", []) or [] if isinstance(item, dict)]
    beats = [
        beat
        for block in blocks
        for beat in block.get("beats", []) or []
        if isinstance(beat, dict)
    ]
    if not beats:
        raise ValueError("[FIM_HISTORIA] apareceu sem um quadro V2 anterior.")

    line_id = str(row.get("line_id", "") or "").strip()
    if not line_id:
        raise ValueError("[FIM_HISTORIA] precisa de line_id.")
    if any(str(beat.get("beat_id", "") or "").strip() == line_id for beat in beats):
        raise ValueError(f"[FIM_HISTORIA] duplicou beat_id existente: {line_id}.")

    character = dict(document.get("character") or {})
    actor = str(character.get("character_id", "") or character.get("name", "") or "personagem").strip()
    visible_name = str(character.get("name", "") or actor or "Personagem").strip()
    image_id = str(row.get("image_id", "") or "").strip().replace("\\", "/")

    frame: dict[str, Any] = {
        "frame_id": line_id,
        "description": "",
        "entries": [
            {
                "kind": "fala",
                "actor": actor,
                "instruction": body,
                "line_id": line_id,
                "delivery": "exata",
                "visible_name": visible_name,
                **({"image_id": image_id} if image_id else {}),
            }
        ],
        "is_ending": True,
        "terminal_kind": _TERMINAL_KIND,
        "deterministic": True,
        **({"image_id": image_id} if image_id else {}),
    }

    # O quadro narrativo anterior deve conduzir à despedida, e não terminar antes.
    previous = beats[-1]
    previous["next_beat_id"] = line_id
    previous["allowed_transitions"] = {"engaged": line_id}
    movement = str(previous.get("required_movement", "") or "")
    if movement.startswith(novel_frame_patch._FRAME_PREFIX):
        try:
            payload = json.loads(movement[len(novel_frame_patch._FRAME_PREFIX) :])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("is_ending"):
            payload["is_ending"] = False
            previous["required_movement"] = novel_frame_patch._FRAME_PREFIX + json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            )

    target_block = next(
        (block for block in blocks if previous in (block.get("beats", []) or [])),
        blocks[-1],
    )
    target_block.setdefault("beats", []).append(
        {
            "beat_id": line_id,
            "order": max((int(beat.get("order", 0) or 0) for beat in beats), default=0) + 1,
            "type": "dialogue",
            "required_movement": novel_frame_patch._FRAME_PREFIX
            + json.dumps(frame, ensure_ascii=False, separators=(",", ":")),
            "canonical_line": body,
            "dramatic_direction": "Despedida final autoral; não usar modelo.",
            "next_beat_id": "",
            "allowed_transitions": {},
            "max_questions": 0,
            "max_sentences": 2,
            "status": "active",
        }
    )
    return document


def _terminal_frame(script: Any, target_id: str) -> tuple[Any, dict[str, Any]] | None:
    movement = (
        first_frame_movement(script)[1]
        if not str(target_id or "").strip()
        else movement_from_script(script, target_id)
    )
    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict) or str(frame.get("terminal_kind", "")) != _TERMINAL_KIND:
        return None
    return movement, frame


def _terminal_content(frame: dict[str, Any], *, protagonist: str) -> str:
    frame_id = str(frame.get("frame_id", "") or "").strip()
    entries = [entry for entry in frame.get("entries", []) or [] if isinstance(entry, dict)]
    if not frame_id or not entries:
        raise ValueError("Quadro [FIM_HISTORIA] compilado de forma inválida.")
    entry = entries[0]
    actor = str(entry.get("actor", "") or "personagem").strip()
    visible_name = str(entry.get("visible_name", "") or actor or "Personagem").strip()
    body = str(entry.get("instruction", "") or "").replace("{{nome}}", protagonist).strip()
    if not body:
        raise ValueError("[FIM_HISTORIA] com quadro visual precisa conter uma despedida.")
    return (
        f"[QUADRO {frame_id}]\n"
        f"[FALA {actor}|{visible_name}]\n{body}\n"
        "[/QUADRO]"
    )


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    original_mark = editorial_content._mark_explicit_story_end

    @wraps(original_mark)
    def mark_story_end(document: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
        found = _story_end_rows(rows)
        if not found:
            return original_mark(document, rows)
        if len(found) > 1:
            raise ValueError("O roteiro V2 deve possuir no máximo uma tag [FIM_HISTORIA].")
        marker_index, row, match = found[0]
        active = _active_sorted(rows)
        if marker_index != len(active) - 1:
            raise ValueError("[FIM_HISTORIA] deve ser a última linha ativa do roteiro V2.")
        body = str(match.group("body") or "").strip()
        if not body:
            return original_mark(document, rows)
        return _append_terminal_card(document, row=row, body=body)

    editorial_content._mark_explicit_story_end = mark_story_end

    cls = FletRunService
    original_generate = cls._generate

    @wraps(original_generate)
    def generate(self: Any, **kwargs: Any):
        terminal = _terminal_frame(kwargs["script"], str(kwargs.get("target_id", "")))
        if terminal is None:
            return original_generate(self, **kwargs)

        movement, frame = terminal
        user = kwargs["user"]
        context = kwargs["context"]
        state = kwargs["state"]
        messages = kwargs["messages"]
        profile = kwargs["profile"]
        target_id = str(frame.get("frame_id", "") or kwargs.get("target_id", "")).strip()
        protagonist = str(profile.get("preferred_name") or user.display_name or "Você").strip() or "Você"
        content = _terminal_content(frame, protagonist=protagonist)

        updated_state = state.copy()
        updated_state.step_index += 1
        updated_state.consumed_orders.append(updated_state.step_index)
        # Persista a despedida antes de concluir a run. Se houver falha de escrita,
        # o usuário não perde o quadro terminal nem o crédito por uma conclusão parcial.
        updated_state.finished = False
        entries = [entry for entry in frame.get("entries", []) or [] if isinstance(entry, dict)]
        actor = str(entries[0].get("actor", "") if entries else "") or "character"
        metadata: dict[str, object] = {
            "character_id": actor,
            "editorial_node": target_id,
            "editorial_block": movement.block_id,
            "novel_v2": True,
            "novel_movement": True,
            "novel_frame": True,
            "novel_terminal_frame": True,
            "story_end_card": True,
            "deterministic_terminal": True,
            "input_source": "flet_api",
        }
        memory = persistent_profile_payload(profile)
        if memory and recover_persistent_profile(messages) is None:
            metadata["immersive_profile"] = memory

        context = persist_assistant_message(
            self.repository,
            context=context,
            user=user,
            state=updated_state,
            assistant_text=content,
            assistant_metadata=metadata,
            secrets=self.secrets,
        )
        messages.append({"role": "assistant", "content": content, **metadata})

        updated_state.finished = True
        context = self._finish_loaded_run(
            context=context,
            user_id=user.user_id,
            package_id=kwargs["package"].manifest.package_id,
            block_id=movement.block_id,
            beat_id=target_id,
        )
        return context, updated_state, messages

    setattr(generate, "_story_end_card", True)
    cls._generate = generate
    _INSTALLED = True


__all__ = [
    "install",
    "_append_terminal_card",
    "_terminal_content",
    "_terminal_frame",
]
