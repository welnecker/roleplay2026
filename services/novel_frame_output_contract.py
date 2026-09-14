from __future__ import annotations

import unicodedata
from typing import Any

from services import novel_frame_patch
from services.novel_frame_reveal import frame_id, normalize_frame_markers
from roleplay_shared.onomatopoeia import effect_from_mapping


class FrameOutputContractError(ValueError):
    pass


def frame_generation_instruction(attempt: int = 0) -> str:
    instruction = "Avance a novela executando somente o quadro atual."
    if int(attempt) > 0:
        instruction += (
            " A resposta anterior violou a correspondência estrutural 1:1. "
            "Emita uma saída para cada entry autoral, com o mesmo tipo e actor, "
            "na mesma ordem e sem criar nenhuma entry. Respeite a modalidade "
            "delivery de cada fala."
        )
    return instruction


def _plain(value: object) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold().strip()


def _signature(kind: object, actor: object) -> tuple[str, str]:
    return _plain(kind), _plain(actor)


def _restore_exact_speech(
    expected_entries: list[dict[str, Any]],
    selected: list[tuple[str, str, str, str]],
) -> list[tuple[str, str, str, str]]:
    restored: list[tuple[str, str, str, str]] = []
    for authored, generated in zip(expected_entries, selected):
        if (
            _plain(authored.get("kind", "")) == "fala"
            and _plain(authored.get("delivery", "")) == "exata"
        ):
            expected_body = str(authored.get("instruction", "") or "").strip()
            restored.append((*generated[:3], expected_body))
        else:
            restored.append(generated)
    return restored



def frame_requires_generation(movement: Any) -> bool:
    """Retorna True somente quando o quadro contém fala interpretada."""

    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict):
        return True
    return any(
        _plain(entry.get("kind", "")) == "fala"
        and _plain(entry.get("delivery", "")) == "interpretada"
        for entry in frame.get("entries", []) or []
        if isinstance(entry, dict)
    )


def _compose_frame_content(
    frame: dict[str, Any],
    *,
    character_name: str,
    user_name: str,
    actor_names: dict[str, str] | None,
    interpreted: dict[str, str],
) -> str:
    protagonist = str(user_name or "Você").strip() or "Você"

    def personalized(value: object) -> str:
        return str(value or "").replace("{{nome}}", protagonist).strip()

    output = [f"[QUADRO {str(frame.get('frame_id', '') or '').strip()}]"]
    description = personalized(frame.get("description", ""))
    if description:
        output.extend(("[DESCRIÇÃO]", description))

    for entry in frame.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        kind = _plain(entry.get("kind", ""))
        if kind not in {"fala", "pensamento"}:
            continue
        actor = str(entry.get("actor", "") or "").strip()
        visible_name = novel_frame_patch._actor_visible_name(
            actor,
            character_name=character_name,
            user_name=protagonist,
            actor_names=actor_names,
        )
        for raw_effect in entry.get("effects_before", []) or []:
            if isinstance(raw_effect, dict):
                effect = effect_from_mapping(raw_effect)
                output.append(f"[{effect.canonical_header()}]")
        label = "PENSAMENTO" if kind == "pensamento" else "FALA"
        actor_spec = actor + (f"|{visible_name}" if visible_name else "")
        line_id = str(entry.get("line_id", "") or "").strip()
        body = (
            interpreted.get(line_id, "")
            if kind == "fala" and _plain(entry.get("delivery", "")) == "interpretada"
            else personalized(entry.get("instruction", ""))
        )
        if not body:
            raise FrameOutputContractError(f"{line_id or actor}: conteúdo vazio no quadro.")
        output.extend((f"[{label} {actor_spec}]", body.strip()))

    output.append("[/QUADRO]")
    return "\n".join(output)


def authored_frame_content(
    movement: Any,
    *,
    character_name: str,
    user_name: str,
    actor_names: dict[str, str] | None = None,
) -> str:
    """Serializa um quadro fechado sem chamar o modelo de linguagem."""

    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict):
        raise FrameOutputContractError("O movimento não contém um quadro V2 autoral.")
    if frame_requires_generation(movement):
        raise FrameOutputContractError("O quadro contém fala interpretada e exige geração.")
    return _compose_frame_content(
        frame,
        character_name=character_name,
        user_name=user_name,
        actor_names=actor_names,
        interpreted={},
    )


def interpreted_lines_prompt(
    movement: Any,
    *,
    character_name: str,
    user_name: str,
    actor_names: dict[str, str] | None = None,
    recent_context: str = "",
) -> str:
    """Cria um prompt curto restrito às falas interpretadas do quadro."""

    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict):
        raise FrameOutputContractError("O movimento não contém um quadro V2 autoral.")
    protagonist = str(user_name or "Você").strip() or "Você"
    context_lines = []
    targets = []
    for entry in frame.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        kind = _plain(entry.get("kind", ""))
        actor = str(entry.get("actor", "") or "").strip()
        instruction = str(entry.get("instruction", "") or "").replace(
            "{{nome}}", protagonist
        ).strip()
        if kind == "fala" and _plain(entry.get("delivery", "")) == "interpretada":
            targets.append(
                {
                    "line_id": str(entry.get("line_id", "") or "").strip(),
                    "actor": actor,
                    "visible_name": novel_frame_patch._actor_visible_name(
                        actor,
                        character_name=character_name,
                        user_name=protagonist,
                        actor_names=actor_names,
                    ),
                    "instruction": instruction,
                }
            )
        else:
            context_lines.append(f"{kind}:{actor}: {instruction}")

    if not targets:
        raise FrameOutputContractError("O quadro não possui fala interpretada.")

    target_text = "\n".join(
        f"- {item['line_id']} | {item['visible_name']}: {item['instruction']}"
        for item in targets
    )
    context_text = "\n".join(context_lines)
    previous = str(recent_context or "").strip()[-2000:]
    return f"""Você escreve somente as falas interpretadas de um quadro de visual novel.
Personagem principal: {character_name}. Protagonista: {protagonist}.
Descrição do quadro: {str(frame.get('description', '') or '').replace('{{nome}}', protagonist)}
Contexto autoral do quadro:
{context_text}
Contexto recente:
{previous}

Transforme cada orientação abaixo em uma fala curta, natural e coerente, preservando intenção, intensidade e personalidade:
{target_text}

Não reescreva descrição, pensamentos ou falas já prontas. Não crie ações nem linhas.
Responda exatamente uma vez para cada line_id, nesta ordem:
[FALA_INTERPRETADA <line_id>]
<somente a fala final>
[/FALA_INTERPRETADA]""".strip()


def merge_interpreted_lines(
    movement: Any,
    generated: str,
    *,
    character_name: str,
    user_name: str,
    actor_names: dict[str, str] | None = None,
) -> str:
    """Valida as falas geradas e as injeta no quadro autoral intacto."""

    import re

    frame = novel_frame_patch._frame_from_movement(movement)
    if not isinstance(frame, dict):
        raise FrameOutputContractError("O movimento não contém um quadro V2 autoral.")
    expected = [
        str(entry.get("line_id", "") or "").strip()
        for entry in frame.get("entries", []) or []
        if isinstance(entry, dict)
        and _plain(entry.get("kind", "")) == "fala"
        and _plain(entry.get("delivery", "")) == "interpretada"
    ]
    pattern = re.compile(
        r"\[FALA_INTERPRETADA\s+([^\]]+)\]\s*(.*?)\s*\[/FALA_INTERPRETADA\]",
        re.DOTALL,
    )
    matches = [(line_id.strip(), body.strip()) for line_id, body in pattern.findall(str(generated or ""))]
    if [line_id for line_id, _body in matches] != expected or any(
        not body for _line_id, body in matches
    ):
        raise FrameOutputContractError(
            "O modelo não devolveu exatamente as falas interpretadas solicitadas."
        )
    return _compose_frame_content(
        frame,
        character_name=character_name,
        user_name=user_name,
        actor_names=actor_names,
        interpreted=dict(matches),
    )


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

    selected = _restore_exact_speech(expected_entries, selected)

    output = [f"[QUADRO {expected_frame_id}]"]
    authored_description = str(frame.get("description", "") or "").strip()
    if authored_description:
        if not description:
            raise FrameOutputContractError("O modelo omitiu a descrição do quadro.")
        output.extend(("[DESCRIÇÃO]", description))
    for authored, (kind, actor, visible_name, body) in zip(expected_entries, selected):
        for raw_effect in authored.get("effects_before", []) or []:
            if isinstance(raw_effect, dict):
                effect = effect_from_mapping(raw_effect)
                output.append(f"[{effect.canonical_header()}]")
        label = "PENSAMENTO" if kind == "pensamento" else "FALA"
        actor_spec = actor + (f"|{visible_name}" if visible_name else "")
        output.extend((f"[{label} {actor_spec}]", body))
    output.append("[/QUADRO]")
    return "\n".join(output)


__all__ = [
    "FrameOutputContractError",
    "authored_frame_content",
    "enforce_frame_output_contract",
    "interpreted_lines_prompt",
    "merge_interpreted_lines",
    "frame_generation_instruction",
    "frame_requires_generation",
]
