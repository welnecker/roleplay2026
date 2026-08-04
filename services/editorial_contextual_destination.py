from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from services.editorial_interaction_context import (
    ResolvedInteractionContext,
    resolve_interaction_context,
)
from services.editorial_runtime_types import EditorialScript, EditorialState

ContextualRoute = Literal["continue", "terminal_yard", "immediate_ending"]


@dataclass(frozen=True, slots=True)
class ContextualDestination:
    route: ContextualRoute = "continue"
    signal: str = ""
    reason: str = ""
    confidence: float = 0.0


def current_interaction_context(
    script: EditorialScript,
    state: EditorialState,
) -> ResolvedInteractionContext:
    beat_id = state.node_id or script.first_beat_id
    beat = script.beats.get(beat_id) or {}
    return resolve_interaction_context(beat.get("interaction_context") or {}, state.facts)


def contextual_classification_required(context: ResolvedInteractionContext) -> bool:
    return bool(
        context.allowed_interactions
        or context.recoverable_tensions
        or context.terminal_violations
        or context.immediate_endings
    )


def build_contextual_classification_prompt(context: ResolvedInteractionContext) -> str:
    """Monta uma classificação sem expor beat_ids ao modelo."""

    def section(title: str, values: tuple[str, ...]) -> list[str]:
        lines = [title]
        lines.extend(f"- {item}" for item in values)
        if not values:
            lines.append("- nenhum sinal declarado")
        return lines

    lines = [
        "Você classifica a compatibilidade de uma fala com o contexto narrativo atual.",
        "Analise intenção, alvo, estágio da relação, consentimento, ambiente e intensidade.",
        "Não classifique apenas por palavras isoladas.",
        "A mesma linguagem pode ser incompatível entre estranhos e compatível após desejo mútuo declarado.",
        "Escolha somente um sinal exatamente como declarado abaixo.",
        "Responda exclusivamente em JSON válido, sem markdown:",
        '{"route":"continue|terminal_yard|immediate_ending","signal":"...","reason":"...","confidence":0.0}',
        "",
        "CONTEXTO:",
        f"- estágio da relação: {context.relationship_stage}",
        f"- ambiente: {context.setting}",
        f"- privacidade: {context.privacy}",
        f"- nível de intimidade: {context.intimacy_level}",
        f"- desejo revelado: {'sim' if context.mary_disclosed_desire else 'não'}",
        f"- atração mútua confirmada: {'sim' if context.mutual_attraction_confirmed else 'não'}",
        "",
    ]
    lines.extend(section("INTERAÇÕES COMPATÍVEIS — route continue:", context.allowed_interactions))
    lines.append("")
    lines.extend(section("TENSÕES RECUPERÁVEIS — route continue:", context.recoverable_tensions))
    lines.append("")
    lines.extend(section("RUPTURAS TERMINAIS — route terminal_yard:", context.terminal_violations))
    lines.append("")
    lines.extend(section("VIOLAÇÕES DE ENCERRAMENTO IMEDIATO — route immediate_ending:", context.immediate_endings))
    lines.extend(
        (
            "",
            "REGRAS:",
            "- Elogio, humor ou flerte compatível não vira ruptura por conter linguagem intensa.",
            "- Proposta sexual explícita pode ser terminal em primeiro contato público e compatível em intimidade já estabelecida.",
            "- Coerção, ameaça ou desrespeito a recusa explícita prevalecem sobre outros sinais.",
            "- Se nenhum sinal declarado se aplicar com segurança, use route continue e signal vazio.",
            "- Nunca invente destino, beat, pátio ou ending.",
        )
    )
    return "\n".join(lines)


def build_contextual_classification_request(user_text: str) -> str:
    return "FALA DO USUÁRIO:\n" + str(user_text or "").strip()


def _allowed_signals(context: ResolvedInteractionContext, route: ContextualRoute) -> set[str]:
    if route == "terminal_yard":
        return set(context.terminal_violations)
    if route == "immediate_ending":
        return set(context.immediate_endings)
    return set((*context.allowed_interactions, *context.recoverable_tensions))


def parse_contextual_destination(
    raw: str,
    context: ResolvedInteractionContext,
) -> ContextualDestination:
    try:
        value = json.loads(str(raw or "").strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return ContextualDestination(reason="invalid_classifier_output")
    if not isinstance(value, Mapping):
        return ContextualDestination(reason="invalid_classifier_output")

    route = str(value.get("route", "continue") or "continue").strip()
    if route not in {"continue", "terminal_yard", "immediate_ending"}:
        return ContextualDestination(reason="invalid_classifier_route")
    typed_route: ContextualRoute = route  # type: ignore[assignment]
    signal = str(value.get("signal", "") or "").strip()
    allowed = _allowed_signals(context, typed_route)
    if signal and signal not in allowed:
        return ContextualDestination(reason="undeclared_classifier_signal")
    if typed_route != "continue" and not signal:
        return ContextualDestination(reason="missing_classifier_signal")

    try:
        confidence = float(value.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    # Destinos terminais exigem confiança explícita. Na dúvida, preserva a run.
    if typed_route != "continue" and confidence < 0.70:
        return ContextualDestination(
            route="continue",
            signal=signal,
            reason="terminal_confidence_below_threshold",
            confidence=confidence,
        )
    return ContextualDestination(
        route=typed_route,
        signal=signal,
        reason=str(value.get("reason", "") or "").strip(),
        confidence=confidence,
    )


def state_with_contextual_destination(
    state: EditorialState,
    destination: ContextualDestination,
) -> EditorialState:
    updated = EditorialState.from_dict(state.to_dict())
    updated.facts["_contextual_route"] = destination.route
    updated.facts["_contextual_signal"] = destination.signal
    updated.facts["_contextual_reason"] = destination.reason
    updated.facts["_contextual_confidence"] = f"{destination.confidence:.3f}"
    return updated


def contextual_target(
    context: ResolvedInteractionContext,
    destination: ContextualDestination,
) -> str:
    if destination.route == "terminal_yard":
        return context.terminal_yard_target
    if destination.route == "immediate_ending":
        return context.immediate_ending_target
    return ""


__all__ = [
    "ContextualDestination",
    "ContextualRoute",
    "build_contextual_classification_prompt",
    "build_contextual_classification_request",
    "contextual_classification_required",
    "contextual_target",
    "current_interaction_context",
    "parse_contextual_destination",
    "state_with_contextual_destination",
]
