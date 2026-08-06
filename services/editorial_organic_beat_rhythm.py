from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from services.editorial_beat_context import BeatContext
from services.editorial_runtime_types import EditorialState


@dataclass(frozen=True, slots=True)
class OrganicBeatFrame:
    title: str
    dramatic_center: str
    semantic_anchor: str
    dramatic_direction: str
    intensity: str
    preferred_sentences: int
    max_internal_pressures: int
    response_curve: tuple[str, ...]
    stop_rule: str
    thought_voice_rule: str


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    raw = document.get("organic_beat_rhythm") or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _target_override(target: Mapping[str, Any]) -> dict[str, Any]:
    raw = target.get("organic_beat_rhythm") or target.get("rhythm") or {}
    return dict(raw) if isinstance(raw, Mapping) else {}


def _intensity(context: BeatContext, state: EditorialState, override: Mapping[str, Any]) -> str:
    explicit = str(override.get("intensity", "") or "").strip()
    if explicit:
        return explicit
    if state.desire >= 8 or state.trust >= 8:
        return "charged"
    if context.dramatic_direction and any(
        term in context.dramatic_direction.casefold()
        for term in ("tensão", "vulner", "urg", "intens", "confissão", "desejo")
    ):
        return "charged"
    return "moderate"


def build_organic_beat_frame(
    document: Mapping[str, Any],
    target: Mapping[str, Any],
    context: BeatContext,
    state: EditorialState,
) -> OrganicBeatFrame:
    policy = _policy(document)
    defaults = policy.get("defaults") or {}
    defaults = dict(defaults) if isinstance(defaults, Mapping) else {}
    override = _target_override(target)

    response_curve = override.get("response_curve") or defaults.get("response_curve") or (
        "react_to_user",
        "compress_relevant_inner_state",
        "deliver_beat_movement",
        "return_turn",
    )
    if isinstance(response_curve, str):
        response_curve = (response_curve,)
    else:
        response_curve = tuple(str(item).strip() for item in response_curve if str(item).strip())

    preferred = int(
        override.get("preferred_sentences", defaults.get("preferred_sentences", 2)) or 2
    )
    preferred = max(1, min(preferred, context.max_sentences or preferred))

    return OrganicBeatFrame(
        title=str(policy.get("title", "CENTRO DRAMÁTICO DO TURNO") or "CENTRO DRAMÁTICO DO TURNO"),
        dramatic_center=context.objective,
        semantic_anchor=context.canonical_line,
        dramatic_direction=context.dramatic_direction,
        intensity=_intensity(context, state, override),
        preferred_sentences=preferred,
        max_internal_pressures=max(
            1,
            int(
                override.get(
                    "max_internal_pressures",
                    defaults.get("max_internal_pressures", 2),
                )
                or 2
            ),
        ),
        response_curve=response_curve,
        stop_rule=str(
            override.get("stop_rule")
            or defaults.get("stop_rule")
            or "Pare assim que o movimento obrigatório estiver realizado com clareza e peso emocional."
        ).strip(),
        thought_voice_rule=str(
            policy.get("thought_voice_rule")
            or "Todo pensamento interno de Mary deve estar em primeira pessoa, como voz íntima em 'eu'; nunca escreva 'Mary pensa', 'Mary sente' ou narração psicológica em terceira pessoa."
        ).strip(),
    )


def render_organic_beat_frame(frame: OrganicBeatFrame) -> str:
    if not frame.dramatic_center and not frame.semantic_anchor:
        return ""

    curve_labels = {
        "react_to_user": "Reaja ao conteúdo específico do usuário sem perder o centro do beat.",
        "compress_relevant_inner_state": (
            "Selecione no máximo os elementos internos realmente úteis e comprima-os na escolha de palavras, no ritmo, no humor, na hesitação, na firmeza ou na vulnerabilidade."
        ),
        "deliver_beat_movement": (
            "Faça a reação convergir para o movimento obrigatório; o beat não é uma frase burocrática adicionada depois da interpretação."
        ),
        "return_turn": "Depois de realizar o movimento, pare e devolva espaço ao usuário.",
    }

    lines = [f"{frame.title}:"]
    if frame.dramatic_center:
        lines.append(f"- Este turno existe para: {frame.dramatic_center}")
    if frame.semantic_anchor:
        lines.append(f"- Referência semântica a incorporar organicamente: {frame.semantic_anchor}")
    if frame.dramatic_direction:
        lines.append(f"- Ênfase autoral: {frame.dramatic_direction}")
    lines.extend(
        (
            f"- Intensidade: {frame.intensity}; intensidade altera peso e franqueza, não autoriza verborragia.",
            f"- Orçamento preferencial: cerca de {frame.preferred_sentences} frase(s), respeitando o limite do beat.",
            f"- Use no máximo {frame.max_internal_pressures} pressão(ões) internas para modular a fala.",
            "- Expanda em direção ao núcleo do beat, nunca para fora dele. Cada frase adicional deve tornar o movimento mais natural, claro ou emocionalmente significativo.",
            "- Não produza uma interpretação interna rica seguida de uma fala pobre. Realize a interpretação por meio do próprio texto do beat.",
            "- Não explique o estado psicológico. Exteriorize apenas vestígios relevantes na forma da fala.",
            f"- {frame.thought_voice_rule}",
        )
    )
    for step in frame.response_curve:
        text = curve_labels.get(step, step)
        if text:
            lines.append(f"- {text}")
    lines.append(f"- Critério de conclusão: {frame.stop_rule}")
    return "\n".join(lines)


__all__ = [
    "OrganicBeatFrame",
    "build_organic_beat_frame",
    "render_organic_beat_frame",
]
