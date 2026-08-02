from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Iterable


LOGGER = logging.getLogger("roleplay2026.pilot")


@dataclass(frozen=True, slots=True)
class GuardedResponse:
    response: str
    repeated_recent_anchor: bool
    used_fallback: bool
    guard_reason: str


def finalize_model_response(
    *,
    raw_response: str,
    cleaned_response: str,
    fallback: str,
    recent_assistant_messages: Iterable[str],
) -> GuardedResponse:
    """Preserva a reação do modelo e encerra sempre no beat canônico."""

    raw = str(raw_response or "").strip()
    cleaned = str(cleaned_response or "").strip()
    safe_fallback = str(fallback or "").strip()
    recent = [str(item or "") for item in recent_assistant_messages]

    if not safe_fallback:
        if not cleaned:
            return GuardedResponse("", False, True, "empty_response")
        repeated = _repeats_recent_anchor(cleaned, recent)
        if repeated:
            return GuardedResponse("", True, True, "repeated_recent_anchor")
        return GuardedResponse(cleaned, False, False, "model_response_accepted")

    source = raw or cleaned
    integrated = _reaction_before_canonical(
        response=source,
        fallback=safe_fallback,
        recent_assistant_messages=recent,
    )
    if integrated:
        repeated = _repeats_recent_anchor(integrated, recent)
        if repeated and _normalize(integrated) != _normalize(safe_fallback):
            return GuardedResponse(
                safe_fallback,
                True,
                True,
                "repeated_recent_anchor",
            )
        used_fallback = _normalize(integrated) == _normalize(safe_fallback)
        return GuardedResponse(
            integrated,
            False,
            used_fallback,
            "canonical_boundary_applied",
        )

    return GuardedResponse(safe_fallback, False, True, "canonical_fallback_only")


def build_turn_diagnostics(
    *,
    user_text: str,
    previous_state: Any,
    turn: Any,
    raw_model_response: str,
    final_response: str,
    fallback: str,
    generation_error: str = "",
    guard_reason: str = "",
    repeated_recent_anchor: bool = False,
    system_prompt: str = "",
) -> dict[str, object]:
    """Cria um retrato compacto e serializável da decisão narrativa do turno."""

    previous_node = str(getattr(previous_state, "node_id", "") or "")
    previous_pending = str(getattr(previous_state, "pending_next_beat_id", "") or "")
    previous_interstitial = int(getattr(previous_state, "interstitial_turns", 0) or 0)
    resulting_state = getattr(turn, "state", None)
    resulting_node = str(getattr(resulting_state, "node_id", "") or "")
    resulting_pending = str(getattr(resulting_state, "pending_next_beat_id", "") or "")
    resulting_interstitial = int(getattr(resulting_state, "interstitial_turns", 0) or 0)
    facts = dict(getattr(resulting_state, "facts", {}) or {})
    user_intent = str(facts.get("_last_user_intent", "") or "")
    scene_location = str(facts.get("_scene_location", "") or "")
    raw = str(raw_model_response or "")
    final = str(final_response or "")
    safe_fallback = str(fallback or "")

    transition_reason = "normal_transition"
    if resulting_pending:
        transition_reason = "organic_interstitial"
    elif str(getattr(turn, "ending_code", "")) == "supermarket_help_declined":
        transition_reason = "respectful_refusal"
    elif previous_node == resulting_node and user_intent in {"question", "postpone", "unclear"}:
        transition_reason = "await_explicit_decision"
    elif bool(getattr(turn, "finished", False)):
        transition_reason = "ending"
    elif previous_pending:
        transition_reason = "resume_pending_beat"
    elif user_intent == "accept" and facts.get("help_to_car") == "accepted":
        transition_reason = "explicit_acceptance"

    return {
        "diagnostic_version": 3,
        "previous_node_id": previous_node,
        "target_id": str(getattr(turn, "target_id", "") or ""),
        "resulting_node_id": resulting_node,
        "previous_pending_beat_id": previous_pending,
        "resulting_pending_beat_id": resulting_pending,
        "previous_interstitial_turns": previous_interstitial,
        "resulting_interstitial_turns": resulting_interstitial,
        "engagement": str(getattr(turn, "engagement", "") or ""),
        "user_intent": user_intent,
        "scene_location": scene_location,
        "transition_reason": transition_reason,
        "finished": bool(getattr(turn, "finished", False)),
        "run_status": str(getattr(turn, "run_status", "") or ""),
        "ending_code": str(getattr(turn, "ending_code", "") or ""),
        "facts": facts,
        "user_text": str(user_text or ""),
        "fallback_text": safe_fallback,
        "raw_model_response": raw,
        "final_response": final,
        "used_fallback": _normalize(final) == _normalize(safe_fallback),
        "model_response_changed": bool(raw) and _normalize(raw) != _normalize(final),
        "repeated_recent_anchor": bool(repeated_recent_anchor),
        "guard_reason": str(guard_reason or ""),
        "generation_error": str(generation_error or ""),
        "system_prompt": str(system_prompt or "")[:12000],
    }


def log_turn(diagnostics: dict[str, object]) -> None:
    try:
        LOGGER.info("pilot_turn %s", json.dumps(diagnostics, ensure_ascii=False, default=str))
    except Exception:
        LOGGER.exception("Não foi possível serializar o diagnóstico do turno")


def log_exception(stage: str, exc: BaseException, **context: object) -> None:
    payload = {"stage": stage, **context}
    LOGGER.exception(
        "pilot_error %s | %s",
        json.dumps(payload, ensure_ascii=False, default=str),
        exc,
    )


def _reaction_before_canonical(
    *,
    response: str,
    fallback: str,
    recent_assistant_messages: list[str],
) -> str:
    """Mantém somente a reação anterior ao beat e reaplica o beat editorial exato."""

    raw = str(response or "").strip()
    safe_fallback = str(fallback or "").strip()
    if not safe_fallback:
        return raw
    if not raw:
        return safe_fallback

    lowered = raw.casefold()
    if any(marker in lowered for marker in ("<end_run", "end_run", "```json", '"event"')):
        return safe_fallback

    without_thought = re.sub(
        r"\[PENSAMENTO\].*?\[/PENSAMENTO\]",
        "",
        raw,
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()

    prefix = _prefix_before_anchor(without_thought, safe_fallback)
    if prefix is None:
        prefix = without_thought

    reaction = _safe_reaction(prefix, recent_assistant_messages)
    if not reaction:
        return safe_fallback
    return f"{reaction}\n\n{safe_fallback}"


def _prefix_before_anchor(text: str, anchor: str) -> str | None:
    """Localiza a fala canônica por sequência de palavras, ignorando pontuação."""

    text_tokens = [
        (match.group(0).casefold(), match.start(), match.end())
        for match in re.finditer(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", str(text or ""))
    ]
    anchor_tokens = [
        match.group(0).casefold()
        for match in re.finditer(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]+", str(anchor or ""))
    ]
    if not text_tokens or not anchor_tokens or len(anchor_tokens) > len(text_tokens):
        return None

    words = [item[0] for item in text_tokens]
    size = len(anchor_tokens)
    for index in range(len(words) - size + 1):
        if words[index : index + size] == anchor_tokens:
            return str(text or "")[: text_tokens[index][1]].strip()
    return None


def _safe_reaction(text: str, recent_assistant_messages: list[str]) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(text or "")) if part.strip()]
    for paragraph in paragraphs:
        if _looks_like_unsafe_narration(paragraph):
            continue
        reaction = _first_sentences(paragraph, limit=2)
        if not reaction or _repeats_recent_anchor(reaction, recent_assistant_messages):
            continue
        return reaction
    return ""


def _looks_like_unsafe_narration(text: str) -> bool:
    patterns = (
        r"\bMary\s+(?:sorri|ri|olha|observa|caminha|segura|respira|inclina|aproxima|afasta|encosta|vira)\b",
        r"\bela\s+(?:sorri|ri|olha|observa|caminha|segura|respira|inclina|aproxima|afasta|encosta|vira)\b",
        r"\b(?:eu\s+)?(?:sorrio|rio|dou um passo|caminho|seguro|ajeito|observo|olho|recuo|respiro|inclino|aproximo|afasto|encosto)\b",
        r"\*[^*]+\*",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _first_sentences(text: str, *, limit: int) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return ""
    pieces = re.split(r"(?<=[.!?])\s+", compact)
    return " ".join(pieces[: max(1, int(limit))]).strip()


def _repeats_recent_anchor(response: str, recent_messages: list[str]) -> bool:
    normalized_response = _normalize(response)
    if not normalized_response:
        return False

    for message in recent_messages[-6:]:
        for unit in _meaningful_units(message):
            if unit in normalized_response:
                return True

    response_units = _meaningful_units(response)
    if not response_units:
        return False
    recent_units = {
        unit
        for message in recent_messages[-6:]
        for unit in _meaningful_units(message)
    }
    return any(unit in recent_units for unit in response_units)


def _meaningful_units(text: str) -> set[str]:
    compact = re.sub(r"\.{2,}", " ", str(text or ""))
    parts = re.split(r"(?<=[!?])\s+|(?<=\.)\s+|\n+", compact)
    result: set[str] = set()
    for part in parts:
        normalized = _normalize(part)
        if len(normalized.split()) >= 6 and len(normalized) >= 36:
            result.add(normalized)
    whole = _normalize(compact)
    if len(whole.split()) >= 6 and len(whole) >= 36:
        result.add(whole)
    return result


def _normalize(text: str) -> str:
    value = str(text or "").casefold()
    value = re.sub(r"\[/?pensamento\]", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[^a-z0-9à-öø-ÿ]+", " ", value)
    return " ".join(value.split())