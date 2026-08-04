from __future__ import annotations

from dataclasses import replace
from typing import Callable

from services.editorial_runtime_types import (
    EditorialEngagement,
    EditorialScript,
    EditorialState,
    EditorialTurn,
)


_PHASE_KEY = "_runtime_phase"
_ACTIVE_YARD_KEY = "_active_yard_id"
_YARD_TURNS_KEY = "_yard_user_turn_count"


def terminal_yards(script: EditorialScript) -> dict[str, dict[str, object]]:
    raw = script.scene.get("terminal_yards") or {}
    return raw if isinstance(raw, dict) else {}


def active_terminal_yard_id(state: EditorialState) -> str:
    if str(state.facts.get(_PHASE_KEY, "") or "") != "terminal_yard":
        return ""
    return str(state.facts.get(_ACTIVE_YARD_KEY, "") or "").strip()


def state_for_target(
    script: EditorialScript,
    state: EditorialState,
    target_id: str,
) -> EditorialState:
    """Sincroniza a fase estrutural com o destino efetivamente escolhido."""

    updated = EditorialState.from_dict(state.to_dict())
    beat = script.beats.get(str(target_id or "")) or {}
    yard_id = str(beat.get("terminal_yard_id", "") or "").strip()
    if yard_id:
        previous_yard = active_terminal_yard_id(updated)
        updated.facts[_PHASE_KEY] = "terminal_yard"
        updated.facts[_ACTIVE_YARD_KEY] = yard_id
        if previous_yard != yard_id:
            updated.facts[_YARD_TURNS_KEY] = "0"
        else:
            updated.facts.setdefault(_YARD_TURNS_KEY, "0")
        return updated

    if str(target_id or "") in script.endings:
        updated.facts[_PHASE_KEY] = "finished"
        updated.facts.pop(_ACTIVE_YARD_KEY, None)
        updated.facts.pop(_YARD_TURNS_KEY, None)
        return updated

    # Uma ponte entrega uma fala intermediária no beat de origem. Finalizar essa
    # fala não pode apagar a fase antes que o usuário responda novamente.
    if str(updated.facts.get(_PHASE_KEY, "") or "") == "bridge":
        updated.facts.pop(_ACTIVE_YARD_KEY, None)
        updated.facts.pop(_YARD_TURNS_KEY, None)
        return updated

    updated.facts[_PHASE_KEY] = "canonical"
    updated.facts.pop(_ACTIVE_YARD_KEY, None)
    updated.facts.pop(_YARD_TURNS_KEY, None)
    return updated


def decide_terminal_yard_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
    *,
    base_decide: Callable[[EditorialScript, EditorialState, str], EditorialTurn],
    classify_message: Callable[[str], EditorialEngagement],
) -> EditorialTurn | None:
    """Executa o pátio antes de qualquer roteador capaz de retornar ao fluxo principal."""

    yard_id = active_terminal_yard_id(state)
    if not yard_id:
        return None

    definition = terminal_yards(script).get(yard_id)
    if not isinstance(definition, dict):
        raise RuntimeError(f"Estado aponta para pátio terminal inexistente: {yard_id!r}")

    yard_beats = {
        str(item).strip()
        for item in definition.get("beat_ids", []) or []
        if str(item).strip()
    }
    ending_ids = {
        str(item).strip()
        for item in definition.get("ending_ids", []) or []
        if str(item).strip()
    }
    if state.node_id not in yard_beats:
        raise RuntimeError(
            f"Pátio {yard_id!r} ativo, mas node_id está fora dele: {state.node_id!r}"
        )

    working = EditorialState.from_dict(state.to_dict())
    working.pending_next_beat_id = ""
    working.interstitial_turns = max(2, working.interstitial_turns)
    turn = base_decide(script, working, user_text)

    allowed_targets = yard_beats | ending_ids
    if turn.target_id not in allowed_targets:
        raise RuntimeError(
            f"Pátio {yard_id!r} tentou escapar para {turn.target_id!r}; "
            f"destinos permitidos: {sorted(allowed_targets)}"
        )

    updated = EditorialState.from_dict(turn.state.to_dict())
    count = int(state.facts.get(_YARD_TURNS_KEY, "0") or 0) + 1
    updated.facts[_YARD_TURNS_KEY] = str(count)

    min_turns = int(definition.get("min_user_turns", 0) or 0)
    max_turns = int(definition.get("max_user_turns", 0) or 0)
    if turn.target_id in ending_ids and count < min_turns:
        raise RuntimeError(
            f"Pátio {yard_id!r} encerrou com {count} turno(s), abaixo do mínimo {min_turns}."
        )
    if max_turns > 0 and count > max_turns:
        raise RuntimeError(
            f"Pátio {yard_id!r} ultrapassou o máximo de {max_turns} turnos do usuário."
        )

    updated = state_for_target(script, updated, turn.target_id)
    return replace(
        turn,
        engagement=classify_message(user_text),
        state=updated,
    )


__all__ = [
    "active_terminal_yard_id",
    "decide_terminal_yard_turn",
    "state_for_target",
    "terminal_yards",
]
