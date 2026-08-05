from __future__ import annotations

"""Integração do classificador contextual com o player editorial.

O nome do módulo é mantido por compatibilidade, mas a instalação não faz monkey
patch. Ela registra a dependência no motor oficial de turnos.
"""

import streamlit as st

from roleplay.openrouter import OpenRouterError, generate_response
from services.editorial_contextual_orchestration import decide_contextual_editorial_turn
from services.editorial_progression import decide_editorial_progression_turn
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.editorial_turn_engine import configure_editorial_turn_classifier


MODEL_DEFAULT = "google/gemini-3-flash-preview"
_ORIGINAL_DECIDE = decide_editorial_progression_turn
_INSTALLED = False


def _secret_value(name: str, default: str = "") -> str:
    """Lê configuração do Streamlit sem tornar testes/CLI dependentes de secrets.toml.

    O motor editorial é uma API de domínio e pode ser chamado fora do processo
    Streamlit. Ausência do arquivo de segredos significa apenas que a classificação
    remota não está disponível; a progressão normal permanece ativa.
    """

    try:
        value = st.secrets.get(name, default)
    except Exception:
        return default
    return str(value or default).strip()


def _classifier_call(system_prompt: str, request: str) -> str:
    api_key = _secret_value("OPENROUTER_API_KEY")
    model = _secret_value("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT
    if not api_key:
        return "{}"
    try:
        return generate_response(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            history=[],
            user_text=request,
        )
    except OpenRouterError:
        # Falha operacional do classificador preserva a progressão normal.
        return "{}"


def decide_player_editorial_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn:
    """Compatibilidade para chamadas diretas antigas e testes isolados."""

    turn, destination = decide_contextual_editorial_turn(
        script,
        state,
        user_text,
        classifier_call=_classifier_call,
        decide_turn=_ORIGINAL_DECIDE,
    )
    turn.state.facts["_contextual_route"] = destination.route
    turn.state.facts["_contextual_signal"] = destination.signal
    turn.state.facts["_contextual_reason"] = destination.reason
    turn.state.facts["_contextual_confidence"] = f"{destination.confidence:.3f}"
    return turn


def install_contextual_player_cycle() -> None:
    """Registra o classificador no motor oficial sem substituir o runtime."""

    global _INSTALLED
    configure_editorial_turn_classifier(_classifier_call)
    _INSTALLED = True


__all__ = [
    "decide_player_editorial_turn",
    "install_contextual_player_cycle",
]
