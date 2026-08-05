from __future__ import annotations

"""Motor oficial de decisão de turno editorial.

O fluxo público é sempre:

    beat atual -> avaliação da ponte -> próximo beat, mesmo beat, pátio ou ending

O classificador apenas descreve a compatibilidade contextual. O runtime continua
soberano sobre IDs, transições, pátios e encerramentos declarados pelo card.
"""

from collections.abc import Callable

from services.editorial_contextual_orchestration import (
    classify_contextual_destination_for_turn,
)
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


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
) -> EditorialTurn:
    """Executa a ponte contextual antes da progressão editorial normal.

    A classificação é armazenada no estado transitório. A progressão então aplica,
    em ordem, pátio já ativo, destino contextual, decisões declaradas e próximo beat.
    Isso torna a arquitetura reutilizável por qualquer card editorial futuro.
    """

    effective_classifier = classifier_call or _classifier_call
    classified_state, _destination = classify_contextual_destination_for_turn(
        script,
        state,
        user_text,
        classifier_call=effective_classifier,
    )
    return decide_editorial_progression_turn(script, classified_state, user_text)


__all__ = [
    "ClassifierCall",
    "configure_editorial_turn_classifier",
    "decide_editorial_turn",
]
