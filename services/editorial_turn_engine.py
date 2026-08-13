from __future__ import annotations

"""Motor oficial de decisão de turno editorial.

O fluxo público é sempre:

    beat atual -> avaliação da ponte -> próximo beat, mesmo beat, pátio ou ending

O classificador apenas descreve a compatibilidade contextual. O runtime continua
soberano sobre IDs, transições, pátios e encerramentos declarados pelo card.
"""

from collections.abc import Callable
from typing import Mapping, Sequence

from services.editorial_contextual_orchestration import (
    classify_contextual_destination_for_turn,
)
from services.editorial_contextual_destination import (
    ContextualDestination,
    state_with_contextual_destination,
)
from services.editorial_bridge import (
    automatic_gate_enabled,
    automatic_gate_policy,
    bridge_active,
)
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_semantic_reconciliation import (
    build_reconciliation_prompt,
    build_reconciliation_request,
    immediate_reconciliation_steps,
    parse_reconciliation,
    preserve_character_owned_target_beats,
    reconciliation_terminal_destination,
    state_with_reconciliation,
)


ClassifierCall = Callable[[str, str], str]


def _continue_classifier(_system_prompt: str, _request: str) -> str:
    """Fallback seguro para ferramentas e testes sem cliente de modelo registrado."""

    return "{}"


_classifier_call: ClassifierCall = _continue_classifier


def configure_editorial_turn_classifier(classifier_call: ClassifierCall | None) -> None:
    """Registra explicitamente a dependência de classificação do player.

    Não substitui funções de outros módulos e não depende da ordem de importação.
    Passar ``None`` restaura o fallback conservador, que preserva a progressão.
    """

    global _classifier_call
    _classifier_call = classifier_call or _continue_classifier


def decide_editorial_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    classifier_call: ClassifierCall | None = None,
    history: Sequence[Mapping[str, str]] = (),
) -> EditorialTurn:
    """Executa a ponte contextual antes da progressão editorial normal.

    A classificação é armazenada no estado transitório. A progressão então aplica,
    em ordem, pátio já ativo, destino contextual, decisões declaradas e próximo beat.
    Isso torna a arquitetura reutilizável por qualquer card editorial futuro.
    """

    effective_classifier = classifier_call or _classifier_call
    reconciled_state = EditorialState.from_dict(state.to_dict())
    if str(state.facts.get("_runtime_phase", "") or "") != "terminal_yard":
        steps = immediate_reconciliation_steps(script, state)
        if steps:
            raw = effective_classifier(
                build_reconciliation_prompt(script, state),
                build_reconciliation_request(user_text, history),
            )
            reconciliation = parse_reconciliation(
                raw,
                allowed_step_ids=(item["step_id"] for item in steps),
                active_response_step_ids=(
                    item["step_id"]
                    for item in steps
                    if item.get("kind") == "active_beat_response"
                ),
                user_text=user_text,
                history=history,
            )
            if automatic_gate_enabled(script):
                reconciliation = preserve_character_owned_target_beats(
                    reconciliation,
                    steps,
                )
            reconciled_state = state_with_reconciliation(state, reconciliation)
            active_id = (
                str(state.facts.get("_bridge_origin_beat_id", "") or "").strip()
                if bridge_active(state)
                else str(state.node_id or "").strip()
            )
            active_assessment = next(
                (item for item in reconciliation.steps if item.step_id == active_id),
                None,
            )
            if automatic_gate_enabled(script) and active_assessment is not None:
                gate_policy = automatic_gate_policy(script)
                automatic_retry = (
                    bridge_active(state)
                    and str(state.facts.get("_automatic_gate_active", "") or "") == "true"
                )
                attempts = int(state.facts.get("_automatic_gate_attempts", "0") or 0)
                max_redirects = max(0, int(gate_policy.get("max_redirects", 1) or 0))
                failure_signal = ""
                if active_assessment.status == "contradicted":
                    failure_signal = str(
                        gate_policy.get("on_refusal", "required_outcome_refused")
                        or "required_outcome_refused"
                    )
                elif (
                    automatic_retry
                    and attempts >= max_redirects
                    and active_assessment.status in {"pending", "partial"}
                ):
                    failure_signal = str(
                        gate_policy.get("on_unresolved", "required_outcome_unresolved")
                        or "required_outcome_unresolved"
                    )
                if failure_signal:
                    reconciled_state = state_with_contextual_destination(
                        reconciled_state,
                        ContextualDestination(
                            route="immediate_ending",
                            signal=failure_signal,
                            reason=active_assessment.reason or failure_signal,
                            confidence=1.0,
                        ),
                    )
                    return decide_editorial_progression_turn(
                        script, reconciled_state, user_text
                    )
            terminal, signal, reason = reconciliation_terminal_destination(
                reconciled_state
            )
            if terminal:
                reconciled_state = state_with_contextual_destination(
                    reconciled_state,
                    ContextualDestination(
                        route="terminal_yard",
                        signal=signal,
                        reason=reason,
                        confidence=1.0,
                    ),
                )
                return decide_editorial_progression_turn(
                    script, reconciled_state, user_text
                )
    classified_state, _destination = classify_contextual_destination_for_turn(
        script,
        reconciled_state,
        user_text,
        classifier_call=effective_classifier,
    )
    return decide_editorial_progression_turn(script, classified_state, user_text)


__all__ = [
    "ClassifierCall",
    "configure_editorial_turn_classifier",
    "decide_editorial_turn",
]
