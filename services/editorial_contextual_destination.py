from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Mapping

from services.editorial_interaction_context import (
    ResolvedInteractionContext,
    resolve_interaction_context,
)
from services.editorial_runtime_types import (
    EditorialScript,
    EditorialState,
    EditorialTurn,
)
from services.editorial_terminal_yard import state_for_target, terminal_yards

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
            "- Não trate como ruptura informação que responde diretamente a uma pergunta feita pela personagem.",
            "- reconhecimento casual decorrente de local compartilhado, vizinhança ou convivência pública preserva a continuidade.",
            "- Alegar que já viu a personagem não equivale a conhecer sua vida privada, rotina, endereço exato ou segredos.",
            "- Conhecimento ambíguo deve usar tensão recuperável e permitir uma clarificação antes de qualquer encerramento.",
            "- Ruptura por conhecimento exige conhecimento privado, invasivo, vigilância, rastreamento ou falsa intimidade persistente.",
            "- Na dúvida entre continuidade e ruptura, prefira continuidade ou clarificação; pátio exige incompatibilidade demonstrada.",
            "- A fala do usuário não pode criar uma nova trajetória narrativa fora dos beats e transições declarados.",
            "- hospital, ambulância, médico, investigação, viagem, novo encontro ou prática sexual não prevista não devem ser desenvolvidos pelo modelo.",
            "- Uma primeira sugestão recuperável pode ser recusada e realinhada ao movimento atual sem criar outro enredo.",
            "- persistência ou fato já consolidado que torna o próximo beat impossível deve usar route terminal_yard.",
            "- Não contradiga fatos declarados pelo usuário apenas para preservar o beat; se o fato inviabiliza o roteiro, encerre pelo pátio.",
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


def destination_from_state(state: EditorialState) -> ContextualDestination:
    route = str(state.facts.get("_contextual_route", "continue") or "continue")
    if route not in {"continue", "terminal_yard", "immediate_ending"}:
        route = "continue"
    try:
        confidence = float(state.facts.get("_contextual_confidence", "0") or 0.0)
    except ValueError:
        confidence = 0.0
    return ContextualDestination(
        route=route,  # type: ignore[arg-type]
        signal=str(state.facts.get("_contextual_signal", "") or ""),
        reason=str(state.facts.get("_contextual_reason", "") or ""),
        confidence=max(0.0, min(1.0, confidence)),
    )


def contextual_target(
    context: ResolvedInteractionContext,
    destination: ContextualDestination,
) -> str:
    if destination.route == "terminal_yard":
        return context.terminal_yard_target
    if destination.route == "immediate_ending":
        return context.immediate_ending_target
    return ""


def _dialogue_data(beat: Mapping[str, Any]) -> tuple[str, str]:
    for unit in beat.get("units", []) or []:
        if isinstance(unit, Mapping) and str(unit.get("kind", "")) == "dialogue":
            return (
                str(unit.get("anchor") or unit.get("text") or "").strip(),
                str(unit.get("instruction") or "").strip(),
            )
    return "", ""


def _clear_destination_facts(state: EditorialState) -> None:
    for key in (
        "_contextual_route",
        "_contextual_signal",
        "_contextual_reason",
        "_contextual_confidence",
    ):
        state.facts.pop(key, None)


def decide_contextual_destination_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn | None:
    """Aplica somente destinos validados e declarados pelo card."""

    destination = destination_from_state(state)
    if destination.route == "continue":
        return None
    context = current_interaction_context(script, state)
    target_id = contextual_target(context, destination)
    if not target_id:
        raise RuntimeError(
            f"Rota contextual {destination.route!r} não possui destino declarado no contexto atual."
        )

    updated = EditorialState.from_dict(state.to_dict())
    _clear_destination_facts(updated)
    updated.pending_next_beat_id = ""
    updated.interstitial_turns = 0

    if destination.route == "immediate_ending":
        ending = script.endings.get(target_id)
        if ending is None:
            raise RuntimeError(f"Encerramento contextual inexistente: {target_id!r}")
        updated.node_id = target_id
        updated.finished = True
        updated.run_status = str(ending.get("run_status", "terminated") or "terminated")
        updated.ending_code = str(ending.get("ending_code", target_id) or target_id)
        updated = state_for_target(script, updated, target_id)
        fallback = str((ending.get("visible_delivery") or {}).get("text", "") or "").strip()
        prompt = (
            "Você é a personagem do card. Encerre imediatamente a interação, sem convite para continuar.\n"
            f"FALA DO USUÁRIO: {user_text}\n"
            f"RUPTURA DETECTADA: {destination.signal}\n"
            f"REFERÊNCIA DE VOZ: {fallback}"
        )
        return EditorialTurn(
            engagement="hostile",
            target_id=target_id,
            visible_fallback=fallback,
            system_prompt=prompt,
            state=updated,
            finished=True,
            run_status=updated.run_status,
            ending_code=updated.ending_code,
        )

    beat = script.beats.get(target_id)
    if beat is None:
        raise RuntimeError(f"Entrada de pátio contextual inexistente: {target_id!r}")
    yard_id = str(beat.get("terminal_yard_id", "") or "").strip()
    definition = terminal_yards(script).get(yard_id)
    if not yard_id or not isinstance(definition, dict):
        raise RuntimeError(f"Destino contextual não pertence a um pátio terminal: {target_id!r}")
    if str(definition.get("entry_beat_id", "") or "") != target_id:
        raise RuntimeError(
            f"Destino contextual deve apontar para a entrada do pátio {yard_id!r}: {target_id!r}"
        )

    fallback, instruction = _dialogue_data(beat)
    updated.node_id = target_id
    updated = state_for_target(script, updated, target_id)
    prompt = (
        "Você é a personagem do card. A fala do usuário provocou uma ruptura terminal neste estágio da relação.\n"
        "Inicie o pátio de encerramento. Não volte ao fluxo principal e não premie a ruptura com intimidade.\n"
        "Use somente fatos literalmente presentes na fala do usuário e no motivo classificado.\n"
        "Não amplifique o risco: não invente vigilância, rotina conhecida, endereço exato, casamento conhecido ou intenção oculta.\n"
        f"FALA DO USUÁRIO: {user_text}\n"
        f"RUPTURA DETECTADA: {destination.signal}\n"
        f"JUSTIFICATIVA CLASSIFICADA: {destination.reason}\n"
        f"MOVIMENTO DO PÁTIO: {beat.get('objective', '')}\n"
        f"DIREÇÃO: {instruction}\n"
        f"REFERÊNCIA DE VOZ: {fallback}"
    )
    return EditorialTurn(
        engagement="engaged",
        target_id=target_id,
        visible_fallback=fallback,
        system_prompt=prompt,
        state=updated,
    )


__all__ = [
    "ContextualDestination",
    "ContextualRoute",
    "build_contextual_classification_prompt",
    "build_contextual_classification_request",
    "contextual_classification_required",
    "contextual_target",
    "current_interaction_context",
    "decide_contextual_destination_turn",
    "destination_from_state",
    "parse_contextual_destination",
    "state_with_contextual_destination",
]
