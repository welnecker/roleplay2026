from __future__ import annotations

import json
import logging
from typing import Any


LOGGER = logging.getLogger("roleplay2026.pilot")


def build_turn_diagnostics(
    *,
    user_text: str,
    previous_state: Any,
    turn: Any,
    raw_model_response: str,
    final_response: str,
    fallback: str,
    generation_error: str = "",
) -> dict[str, object]:
    """Cria um retrato compacto e serializável da decisão narrativa do turno."""

    previous_node = str(getattr(previous_state, "node_id", "") or "")
    previous_pending = str(getattr(previous_state, "pending_next_beat_id", "") or "")
    previous_interstitial = int(getattr(previous_state, "interstitial_turns", 0) or 0)
    resulting_state = getattr(turn, "state", None)
    resulting_node = str(getattr(resulting_state, "node_id", "") or "")
    resulting_pending = str(getattr(resulting_state, "pending_next_beat_id", "") or "")
    resulting_interstitial = int(getattr(resulting_state, "interstitial_turns", 0) or 0)
    raw = str(raw_model_response or "")
    final = str(final_response or "")
    safe_fallback = str(fallback or "")

    return {
        "diagnostic_version": 1,
        "previous_node_id": previous_node,
        "target_id": str(getattr(turn, "target_id", "") or ""),
        "resulting_node_id": resulting_node,
        "previous_pending_beat_id": previous_pending,
        "resulting_pending_beat_id": resulting_pending,
        "previous_interstitial_turns": previous_interstitial,
        "resulting_interstitial_turns": resulting_interstitial,
        "engagement": str(getattr(turn, "engagement", "") or ""),
        "finished": bool(getattr(turn, "finished", False)),
        "run_status": str(getattr(turn, "run_status", "") or ""),
        "ending_code": str(getattr(turn, "ending_code", "") or ""),
        "facts": dict(getattr(resulting_state, "facts", {}) or {}),
        "user_text": str(user_text or ""),
        "fallback_text": safe_fallback,
        "raw_model_response": raw,
        "final_response": final,
        "used_fallback": final.strip() == safe_fallback.strip(),
        "model_response_changed": bool(raw) and raw.strip() != final.strip(),
        "generation_error": str(generation_error or ""),
    }


def log_turn(diagnostics: dict[str, object]) -> None:
    """Envia o diagnóstico para os logs do processo sem interromper a história."""

    try:
        LOGGER.info("pilot_turn %s", json.dumps(diagnostics, ensure_ascii=False, default=str))
    except Exception:
        LOGGER.exception("Não foi possível serializar o diagnóstico do turno")


def log_exception(stage: str, exc: BaseException, **context: object) -> None:
    """Registra exceções com estágio e contexto narrativo relevante."""

    payload = {"stage": stage, **context}
    LOGGER.exception(
        "pilot_error %s | %s",
        json.dumps(payload, ensure_ascii=False, default=str),
        exc,
    )
