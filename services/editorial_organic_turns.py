from __future__ import annotations

from typing import Any

from services.editorial_message_policy import classify_contextual_editorial_message
from services.editorial_routing import normal_editorial_target
from services.editorial_runtime_types import EditorialScript, EditorialState, EditorialTurn
from services.organic_interaction import detect_organic_signal, render_facts


def _organic_policy(script: EditorialScript) -> dict[str, Any]:
    policy = script.raw.get("organic_slack") or {}
    return policy if isinstance(policy, dict) else {}


def _strict_canonical_policy(script: EditorialScript) -> dict[str, Any]:
    policy = _organic_policy(script).get("strict_canonical") or {}
    return policy if isinstance(policy, dict) else {}


def is_strict_canonical_beat(script: EditorialScript, beat_id: str) -> bool:
    clean = str(beat_id or "").strip()
    policy = _strict_canonical_policy(script)
    beat_ids = {
        str(item).strip()
        for item in policy.get("beat_ids", []) or []
        if str(item).strip()
    }
    prefixes = tuple(
        str(item).strip()
        for item in policy.get("beat_prefixes", []) or []
        if str(item).strip()
    )
    return clean in beat_ids or any(clean.startswith(prefix) for prefix in prefixes)


def _excluded_from_organic_slack(script: EditorialScript, beat_id: str) -> bool:
    excluded = {
        str(item).strip()
        for item in _organic_policy(script).get("excluded_beats", []) or []
        if str(item).strip()
    }
    return str(beat_id or "").strip() in excluded


def _character_name(script: EditorialScript) -> str:
    character = script.raw.get("character") or {}
    if isinstance(character, dict):
        name = str(character.get("name", "") or "").strip()
        if name:
            return name
    return "A personagem"


def organic_editorial_turn(
    script: EditorialScript,
    state: EditorialState,
    user_text: str,
) -> EditorialTurn | None:
    if (
        not bool(_organic_policy(script).get("enabled", False))
        or state.pending_next_beat_id
        or state.interstitial_turns >= 1
    ):
        return None

    current_id = state.node_id or script.first_beat_id
    if _excluded_from_organic_slack(script, current_id) or is_strict_canonical_beat(
        script, current_id
    ):
        return None

    signal = detect_organic_signal(user_text, state.facts)
    if signal is None or signal.kind != "free_reaction":
        return None

    engagement = classify_contextual_editorial_message(user_text)
    if engagement in {"hostile", "mocking"}:
        return None

    next_id = normal_editorial_target(script, state, engagement)
    if not next_id:
        return None

    updated = EditorialState.from_dict(state.to_dict())
    updated.facts = signal.facts
    updated.facts["_organic_interstitial"] = "true"
    updated.pending_next_beat_id = next_id
    updated.interstitial_turns = 1
    prompt = (
        f"Você é {_character_name(script)}. Este é um TURNO ORGÂNICO INTERMEDIÁRIO.\n"
        "Responda somente ao que o usuário acabou de dizer, com liberdade emocional e continuidade.\n"
        "Permaneça no mesmo local, momento e eixo narrativo.\n"
        "Não execute, não cite, não parafraseie e não misture a próxima linha canônica.\n"
        "Não avance tempo, local ou acontecimento. A próxima linha do roteiro será retomada em outro turno.\n"
        f"FATOS CONFIRMADOS: {render_facts(updated.facts)}\n"
        f"MENSAGEM DO USUÁRIO: {user_text}\n"
        f"ORIENTAÇÃO DE REAÇÃO: {signal.instruction}"
    )
    return EditorialTurn(
        engagement=engagement,  # type: ignore[arg-type]
        target_id=current_id,
        visible_fallback=signal.fallback,
        system_prompt=prompt,
        state=updated,
    )


__all__ = ["is_strict_canonical_beat", "organic_editorial_turn"]
