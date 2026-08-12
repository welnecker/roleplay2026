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
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_semantic_reconciliation import (
    build_reconciliation_prompt,
    build_reconciliation_request,
    immediate_reconciliation_steps,
    parse_reconciliation,
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
                user_text=user_text,
                history=history,
            )
            reconciled_state = state_with_reconciliation(state, reconciliation)
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
