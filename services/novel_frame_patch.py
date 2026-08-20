from __future__ import annotations

import json
import re
import unicodedata
from copy import deepcopy
from html import escape
from typing import Any, Iterable

_FRAME_PREFIX = "NOVEL_FRAME_V2\n"
_BALLOON_ACTOR_SUFFIX = "_balao"
_MARKER = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$", re.DOTALL)
_OUTPUT_MARKER = re.compile(r"^\s*\[([^\]]+)\]\s*$", re.MULTILINE)

_installed = False
_original_compile_spreadsheet_story = None
_original_build_novel_prompt = None
_original_render_dialogue_html = None


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold().strip()


def _actor_balloon_directive(actor: str) -> tuple[str, bool]:
    """Separa a identidade do ator da diretiva visual ``_balao``."""

    raw = str(actor or "").strip()
    if _plain(raw).endswith(_BALLOON_ACTOR_SUFFIX):
        return raw[: -len(_BALLOON_ACTOR_SUFFIX)].rstrip("_"), True
    return raw, False


def _tag(value: Any) -> tuple[str, str, str]:
    raw = str(value or "").strip()
    match = _MARKER.match(raw)
    if match is None:
        return "", "", raw
    header = match.group(1).strip()
    body = match.group(2).strip()
    parts = header.split(maxsplit=1)
    kind = _plain(parts[0])
    actor = _plain(parts[1]) if len(parts) > 1 else ""
    return kind, actor, body


def is_novel_frame_rows(rows: Iterable[dict[str, Any]]) -> bool:
    active = [
        dict(row)
        for row in rows
        if str(row.get("status", "active") or "active").strip().casefold() == "active"
    ]
    if not active:
        return False
    kinds = [_tag(row.get("instruction"))[0] for row in active]
    return "descricao" in kinds and any(
        kind in {"fala", "pensamento"} and bool(_tag(row.get("instruction"))[1])
        for row, kind in zip(active, kinds)
    )


def _frame_id_from_description(line_id: str, index: int) -> str:
    clean = str(line_id or "").strip()
    suffix = "_descricao"
    if _plain(clean).endswith(suffix):
        return clean[: -len(suffix)]
    return clean or f"quadro_{index:03d}"


def _active_sorted(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        dict(row)
        for row in rows
        if str(row.get("status", "active") or "active").strip().casefold() == "active"
    ]
    selected.sort(key=lambda row: (int(row.get("order", 0) or 0), str(row.get("line_id", ""))))
    return selected


def compile_novel_frame_story(
    base_document: dict[str, Any],
    rows: Iterable[dict[str, Any]],
    *,
    script_version: str,
) -> dict[str, Any]:
    source_rows = _active_sorted(rows)
    frames: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    seen_line_ids: set[str] = set()

    for row in source_rows:
        line_id = str(row.get("line_id", "") or "").strip()
        if not line_id or line_id in seen_line_ids:
            raise ValueError(f"line_id ausente ou duplicado: {line_id!r}")
        seen_line_ids.add(line_id)
        kind, actor, text = _tag(row.get("instruction"))

        if kind == "descricao":
            current = {
                "frame_id": _frame_id_from_description(line_id, len(frames) + 1),
                "description": text,
                "entries": [],
            }
            frames.append(current)
            continue

        if kind not in {"fala", "pensamento"}:
            continue
        if not actor:
            raise ValueError(f"{line_id}: {kind.upper()} precisa identificar o personagem.")
        if current is None:
            raise ValueError(f"{line_id}: FALA/PENSAMENTO apareceu antes da primeira [DESCRIÇÃO].")
        current["entries"].append(
            {
                "kind": kind,
                "actor": actor,
                "instruction": text,
                "line_id": line_id,
            }
        )

    if not frames:
        raise ValueError("Roteiro V2 não contém quadros com [DESCRIÇÃO].")
    for frame in frames:
        if not frame["entries"]:
            raise ValueError(f"{frame['frame_id']}: quadro sem falas ou pensamentos.")

    first_description = str(frames[0].get("description", "") or "").strip()
    if not first_description:
        raise ValueError("A primeira [DESCRIÇÃO] do roteiro V2 não pode estar vazia.")

    document = deepcopy(base_document)
    document["script_version"] = str(script_version or document.get("script_version", ""))
    document["authoring_source"] = "spreadsheet_novel_frame_v2"
    block = {
        "block_id": "novel_v2_frames",
        "order": 1,
        "title": "Novela",
        "scene_introduction": first_description,
        "entry_beat_id": str(frames[0]["frame_id"]),
        "max_movements_per_response": 1,
        "max_questions_per_response": 0,
        "rules": ["Cada avanço revela um quadro completo multipersonagem."],
        "beats": [],
    }

    for index, frame in enumerate(frames):
        next_id = str(frames[index + 1]["frame_id"]) if index + 1 < len(frames) else ""
        payload_frame = deepcopy(frame)
        if index == 0:
            # A primeira descrição já é exibida como abertura da história.
            # Mantemos o restante do primeiro quadro para o primeiro clique em Avançar,
            # sem repetir a mesma descrição.
            payload_frame["description"] = ""
        payload = json.dumps(payload_frame, ensure_ascii=False, separators=(",", ":"))
        block["beats"].append(
            {
                "beat_id": str(frame["frame_id"]),
                "order": index + 1,
                "type": "dialogue",
                "required_movement": _FRAME_PREFIX + payload,
                "canonical_line": "",
                "dramatic_direction": "Encene o quadro como uma visual novel/HQ contínua.",
                "next_beat_id": next_id,
                "allowed_transitions": ({"engaged": next_id} if next_id else {}),
                "max_questions": 0,
                "max_sentences": 8,
                "status": "active",
            }
        )

    document["blocks"] = [block]
    return document


def _compile_wrapper(base_document: dict[str, Any], rows: Iterable[dict[str, Any]], *, script_version: str) -> dict[str, Any]:
    materialized = list(rows)
    if is_novel_frame_rows(materialized):
        return compile_novel_frame_story(base_document, materialized, script_version=script_version)
    assert _original_compile_spreadsheet_story is not None
    return _original_compile_spreadsheet_story(
        base_document,
        materialized,
        script_version=script_version,
    )


def _frame_from_movement(movement: Any) -> dict[str, Any] | None:
    instruction = str(getattr(movement, "instruction", "") or "")
    if not instruction.startswith(_FRAME_PREFIX):
        return None
    try:
        raw = json.loads(instruction[len(_FRAME_PREFIX):])
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def _actor_visible_name(actor: str, *, character_name: str, user_name: str) -> str:
    resolved_actor, _impact_balloon = _actor_balloon_directive(actor)
    clean = _plain(resolved_actor)
    if clean in {"usuario", "user", "protagonista", "voce"}:
        return str(user_name or "Você").strip() or "Você"
    if clean in {_plain(character_name), "personagem", "p1"}:
        return character_name
    return str(resolved_actor or "Personagem").strip().replace("_", " ").title()


def build_frame_prompt(
    *,
    character_name: str,
    user_name: str,
    movement: Any,
) -> str:
    frame = _frame_from_movement(movement)
    if frame is None:
        assert _original_build_novel_prompt is not None
        return _original_build_novel_prompt(
            character_name=character_name,
            user_name=user_name,
            movement=movement,
        )

    protagonist = str(user_name or "Você").strip() or "Você"
    normalized = deepcopy(frame)
    normalized["description"] = str(normalized.get("description", "")).replace("{{nome}}", protagonist)
    for entry in normalized.get("entries", []) or []:
        if isinstance(entry, dict):
            entry["instruction"] = str(entry.get("instruction", "")).replace("{{nome}}", protagonist)
            entry["visible_name"] = _actor_visible_name(
                str(entry.get("actor", "")),
                character_name=character_name,
                user_name=protagonist,
            )

    authored = json.dumps(normalized, ensure_ascii=False, indent=2)
    description_contract = (
        "- A descrição deste quadro já foi exibida na abertura. Não gere [DESCRIÇÃO] neste quadro."
        if not str(normalized.get("description", "") or "").strip()
        else "- Gere exatamente uma [DESCRIÇÃO] curta a partir da descrição autoral deste quadro."
    )
    description_format = (
        ""
        if not str(normalized.get("description", "") or "").strip()
        else "[DESCRIÇÃO]\n<descrição encenada>\n\n"
    )
    return f"""MODO NOVELA INTERATIVA V2 — QUADRO MULTIPERSONAGEM

Você encena uma visual novel/HQ contínua. O roteiro abaixo define exatamente os elementos do quadro atual.
O protagonista personalizado é {protagonist}. A personagem principal é {character_name}.

QUADRO AUTORAL:
{authored}

REGRAS DE CONTINUIDADE:
- Leia o histórico como uma única cena em andamento. Este quadro começa exatamente onde o anterior terminou.
- Não recapitule o que já aconteceu e não reinicie a relação entre os personagens.
- Cada instrução de FALA descreve a intenção daquela fala; transforme-a em diálogo oral brasileiro, curto e natural.
- Cada PENSAMENTO é privado do personagem correspondente e pode revelar malícia, desejo, estratégia, dúvida ou interpretação que a fala esconde.
- O pensamento deve acrescentar subtexto; não repita a fala com outras palavras.
- Preserve a progressão psicológica dos personagens de um quadro para o seguinte.
- A fala do protagonista também é roteirizada: escreva-a como participação real dele na cena, sem pedir input ao usuário.
- Não crie perguntas que dependam de resposta fora do quadro. Se uma pergunta existir por estilo, a resposta necessária deve estar no próprio quadro.
- Não invente acontecimentos futuros nem personagens ausentes do quadro.
- Evite verborragia: normalmente 1 frase por fala e 1 frase por pensamento; descrição em 1 ou 2 frases.
- Use o nome {protagonist} com parcimônia; não o repita em todas as falas.
{description_contract}

FORMATO OBRIGATÓRIO — devolva somente isto, sem Markdown adicional:
[QUADRO {normalized.get('frame_id', '')}]
{description_format}Depois, para CADA entry do roteiro, na MESMA ORDEM:
- FALA: [FALA <actor>|<visible_name>] seguido da fala.
- PENSAMENTO: [PENSAMENTO <actor>|<visible_name>] seguido do pensamento.
- Quando o actor terminar em `_balao`, copie esse sufixo literalmente na tag de FALA; ele é uma diretiva visual do roteiro.

Finalize com:
[/QUADRO]

Não omita nenhuma entry e não acrescente outras.
""".strip()


def _prompt_wrapper(*, character_name: str, user_name: str, movement: Any, suppress_user_name: bool = False) -> str:
    if _frame_from_movement(movement) is not None:
        return build_frame_prompt(
            character_name=character_name,
            user_name=user_name,
            movement=movement,
        )
    assert _original_build_novel_prompt is not None
    return _original_build_novel_prompt(
        character_name=character_name,
        user_name=user_name,
        movement=movement,
        suppress_user_name=suppress_user_name,
    )


def _paragraphs(value: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", str(value or "")) if block.strip()]
    return "".join(f"<p>{escape(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def _parse_output(content: str) -> list[tuple[str, str, str, str]] | None:
    value = str(content or "").strip()
    if not value.startswith("[QUADRO ") or "[/QUADRO]" not in value:
        return None
    matches = list(_OUTPUT_MARKER.finditer(value))
    parts: list[tuple[str, str, str, str]] = []
    for index, match in enumerate(matches):
        header = match.group(1).strip()
        if header.startswith("QUADRO ") or header == "/QUADRO":
            continue
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        body = value[body_start:body_end].strip()
        pieces = header.split(maxsplit=1)
        kind = _plain(pieces[0])
        actor = ""
        visible_name = ""
        if len(pieces) > 1:
            actor_spec = pieces[1].strip()
            if "|" in actor_spec:
                actor, visible_name = [item.strip() for item in actor_spec.split("|", 1)]
            else:
                actor = actor_spec
                visible_name = actor_spec
        parts.append((kind, actor, visible_name, body))
    return parts


def render_frame_html(content: str, *, character_name: str) -> str | None:
    parts = _parse_output(content)
    if parts is None:
        return None
    html: list[str] = ['<section class="novel-frame-v2">']
    for kind, actor, visible_name, body in parts:
        if not body:
            continue
        if kind == "descricao":
            html.append(
                '<article class="dialogue-message dialogue-mary">'
                '<div class="dialogue-speaker">Cena</div>'
                f'<div class="dialogue-speech">{_paragraphs(body)}</div>'
                '</article>'
            )
            continue
        if kind == "pensamento":
            label = visible_name or actor or character_name
            html.append(
                '<article class="dialogue-message dialogue-mary">'
                f'<div class="dialogue-speaker">{escape(label)}</div>'
                '<div class="mary-thought">'
                '<div class="mary-thought-label"><span>✦</span> pensamento</div>'
                f'<div class="mary-thought-copy">{_paragraphs(body)}</div>'
                '</div>'
                '</article>'
            )
            continue
        if kind == "fala":
            resolved_actor, impact_balloon = _actor_balloon_directive(actor)
            is_user = _plain(resolved_actor) in {"usuario", "user", "protagonista", "voce"}
            wrapper = "dialogue-message dialogue-user" if is_user else "dialogue-message dialogue-mary"
            if impact_balloon:
                wrapper += " novel-frame-impact-balloon"
            actor_was_used_as_label = _plain(visible_name) == _plain(actor)
            resolved_visible_name = "" if actor_was_used_as_label else visible_name
            label = resolved_visible_name or (
                "Você" if is_user else resolved_actor or character_name
            )
            html.append(
                f'<article class="{wrapper}">'
                f'<div class="dialogue-speaker">{escape(label)}</div>'
                f'<div class="dialogue-speech">{_paragraphs(body)}</div>'
                '</article>'
            )
    html.append("</section>")
    return "".join(html)


def _render_wrapper(role: str, content: str, *, character_name: str = "Mary") -> str:
    frame_html = render_frame_html(content, character_name=character_name)
    if frame_html is not None:
        return frame_html
    assert _original_render_dialogue_html is not None
    return _original_render_dialogue_html(role, content, character_name=character_name)


def install() -> None:
    global _installed
    global _original_compile_spreadsheet_story
    global _original_build_novel_prompt
    global _original_render_dialogue_html
    if _installed:
        return

    from services import dialogue_presentation, editorial_content, novel_v2_adapter

    _original_compile_spreadsheet_story = editorial_content.compile_spreadsheet_story
    _original_build_novel_prompt = novel_v2_adapter.build_novel_prompt
    _original_render_dialogue_html = dialogue_presentation.render_dialogue_html

    editorial_content.compile_spreadsheet_story = _compile_wrapper
    novel_v2_adapter.build_novel_prompt = _prompt_wrapper
    dialogue_presentation.render_dialogue_html = _render_wrapper
    _installed = True


__all__ = [
    "build_frame_prompt",
    "compile_novel_frame_story",
    "install",
    "is_novel_frame_rows",
    "render_frame_html",
]
