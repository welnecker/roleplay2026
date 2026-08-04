from __future__ import annotations

import streamlit as st

from roleplay.openrouter import OpenRouterError, generate_response
from services import editorial_runtime
from services.editorial_contextual_orchestration import decide_contextual_editorial_turn
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn


MODEL_DEFAULT = "google/gemini-3-flash-preview"
_ORIGINAL_DECIDE = editorial_runtime.decide_editorial_turn
_INSTALLED = False


def _classifier_call(system_prompt: str, request: str) -> str:
    api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
    model = str(st.secrets.get("OPENROUTER_MODEL", MODEL_DEFAULT) or MODEL_DEFAULT).strip()
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
        # Falha do classificador não deve encerrar ou corromper a run. O parser
        # converte esta saída em continue; a geração principal mantém seu próprio
        # tratamento operacional de erro.
        return "{}"


def decide_player_editorial_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn:
    turn, destination = decide_contextual_editorial_turn(
        script,
        state,
        user_text,
        classifier_call=_classifier_call,
        decide_turn=_ORIGINAL_DECIDE,
    )
    # Diagnóstico serializável: acompanha o turno até o logger e a persistência.
    turn.state.facts["_contextual_route"] = destination.route
    turn.state.facts["_contextual_signal"] = destination.signal
    turn.state.facts["_contextual_reason"] = destination.reason
    turn.state.facts["_contextual_confidence"] = f"{destination.confidence:.3f}"
    return turn


def install_contextual_player_cycle() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    editorial_runtime.decide_editorial_turn = decide_player_editorial_turn
    _INSTALLED = True


__all__ = [
    "decide_player_editorial_turn",
    "install_contextual_player_cycle",
]
