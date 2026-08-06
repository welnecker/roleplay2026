from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Mapping

_EPISODE_KEY = "_episodic_memory_json"
_DRAFT_KEY = "_episodic_memory_draft_json"
_TURN_KEY = "_episodic_memory_turn"
_BLOCKED_KEY = "_episodic_creativity_blocked"

_STOPWORDS = {
    "a", "ao", "aos", "aquela", "aquele", "aquilo", "as", "assim", "até",
    "com", "como", "da", "das", "de", "dela", "dele", "do", "dos", "e",
    "ela", "ele", "em", "essa", "esse", "esta", "este", "eu", "foi", "isso",
    "já", "mas", "me", "meu", "minha", "na", "nas", "não", "no", "nos",
    "o", "os", "ou", "para", "pela", "pelo", "por", "pra", "que", "se",
    "sem", "ser", "sua", "seu", "também", "te", "tem", "ter", "tu", "um",
    "uma", "você", "vocês"
}

_STRUCTURAL_CONTEXT_KEYS = (
    "_bridge_origin_objective",
    "_bridge_origin_canonical",
    "_bridge_target_objective",
    "_bridge_target_canonical",
)


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("episodic_memory") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    runtime = document.get("runtime_policy") or {}
    nested = runtime.get("episodic_memory") if isinstance(runtime, dict) else {}
    return dict(nested) if isinstance(nested, dict) else {}


def _loads(value: object) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return dict(parsed) if isinstance(parsed, dict) else {}


def _dump(value: Mapping[str, Any]) -> str:
    return json.dumps(dict(value), ensure_ascii=False, separators=(",", ":"))


def _clean(text: str, limit: int = 360) -> str:
    return " ".join(str(text or "").split()).strip()[:limit]


def _normalized_words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    words = re.findall(r"[a-zA-Z0-9]+", normalized.lower())
    return [word for word in words if len(word) >= 4 and word not in _STOPWORDS]


def _anchors(text: str, maximum: int = 8) -> list[str]:
    return list(dict.fromkeys(_normalized_words(text)))[:maximum]


def _matches_active_thread(user_text: str, episode: Mapping[str, Any]) -> bool:
    current = set(_anchors(user_text, maximum=12))
    previous = {str(item) for item in episode.get("anchors", []) or []}
    return bool(current.intersection(previous))


def _structural_anchors(facts: Mapping[str, str]) -> set[str]:
    context = " ".join(str(facts.get(key, "") or "") for key in _STRUCTURAL_CONTEXT_KEYS)
    return set(_anchors(context, maximum=40))


def _is_genuinely_creative_bridge(
    user_text: str,
    facts: Mapping[str, str],
    episode: Mapping[str, Any],
) -> bool:
    """Distingue improviso autoral de uma resposta rotineira ao beat.

    A decisão usa somente a divergência lexical em relação ao movimento de origem
    e ao destino já declarados pela ponte. Não depende de palavras temáticas.
    Continuações do fio ativo permanecem válidas mesmo quando forem curtas.
    """

    if episode and episode.get("status") != "consumed":
        return _matches_active_thread(user_text, episode)

    user_anchors = set(_anchors(user_text, maximum=12))
    if len(user_anchors) < 3:
        return False

    structural = _structural_anchors(facts)
    if not structural:
        return len(user_anchors) >= 4

    overlap = len(user_anchors.intersection(structural)) / len(user_anchors)
    return overlap < 0.5


def _recall_allowed(policy: Mapping[str, Any], beat_id: str) -> bool:
    rules = policy.get("recall", []) or []
    if not rules:
        return True
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        beat_ids = {str(item) for item in rule.get("beat_ids", []) or []}
        prefixes = tuple(str(item) for item in rule.get("beat_prefixes", []) or [])
        if beat_id in beat_ids or any(beat_id.startswith(prefix) for prefix in prefixes):
            return True
    return False


def advance_episode_turn(document: Mapping[str, Any], facts: dict[str, str]) -> int:
    """Avança o relógio episódico uma vez por interação do usuário."""

    if not _policy(document):
        return 0
    value = int(facts.get(_TURN_KEY, "0") or 0) + 1
    facts[_TURN_KEY] = str(value)
    facts[_BLOCKED_KEY] = "false"
    return value


def prepare_bridge_episode(
    document: Mapping[str, Any],
    facts: dict[str, str],
    user_text: str,
    *,
    source_beat_id: str,
) -> str:
    """Reserva o único fio criativo do card ou bloqueia nova bifurcação."""

    policy = _policy(document)
    text = _clean(user_text)
    if not policy or not text:
        return "disabled"

    episode = _loads(facts.get(_EPISODE_KEY, ""))
    if not _is_genuinely_creative_bridge(text, facts, episode):
        facts.pop(_DRAFT_KEY, None)
        return "ignored"

    current_turn = int(facts.get(_TURN_KEY, "0") or 0)
    history_turn_window = max(1, int(policy.get("history_turn_window", 6) or 6))

    if not episode:
        facts[_DRAFT_KEY] = _dump({
            "mode": "new",
            "user_text": text,
            "source_beat_id": str(source_beat_id or ""),
            "turn": current_turn,
            "history_turn_window": history_turn_window,
        })
        return "new"

    if episode.get("status") != "consumed" and _matches_active_thread(text, episode):
        facts[_DRAFT_KEY] = _dump({
            "mode": "continue",
            "user_text": text,
            "source_beat_id": str(source_beat_id or ""),
            "turn": current_turn,
            "history_turn_window": history_turn_window,
        })
        return "continue"

    facts.pop(_DRAFT_KEY, None)
    facts[_BLOCKED_KEY] = "true"
    return "blocked"


def consolidate_bridge_episode(facts: dict[str, str], assistant_text: str) -> None:
    """Consolida usuário + Mary somente depois da resposta ter sido aprovada."""

    draft = _loads(facts.pop(_DRAFT_KEY, ""))
    mary_text = _clean(assistant_text)
    if not draft or not mary_text:
        return

    user_text = _clean(str(draft.get("user_text", "")))
    turn = int(draft.get("turn", 0) or 0)
    window = max(1, int(draft.get("history_turn_window", 6) or 6))
    episode = _loads(facts.get(_EPISODE_KEY, ""))

    # O runtime envia as seis interações anteriores. A troca do turno T ainda
    # aparece no contexto em T + window; só desaparece no turno seguinte.
    eligible_after_turn = turn + window + 1

    if draft.get("mode") == "new" or not episode:
        episode = {
            "episode_id": "creative_episode_001",
            "user_text": user_text,
            "mary_text": mary_text,
            "latest_user_text": user_text,
            "latest_mary_text": mary_text,
            "anchors": _anchors(f"{user_text} {mary_text}"),
            "source_beat_id": str(draft.get("source_beat_id", "")),
            "start_turn": turn,
            "end_turn": turn,
            "eligible_after_turn": eligible_after_turn,
            "status": "dormant",
            "continuations": 0,
        }
    else:
        episode["latest_user_text"] = user_text
        episode["latest_mary_text"] = mary_text
        episode["end_turn"] = turn
        episode["eligible_after_turn"] = eligible_after_turn
        episode["continuations"] = int(episode.get("continuations", 0) or 0) + 1
        episode["status"] = "dormant"
        merged = [
            *[str(item) for item in episode.get("anchors", []) or []],
            *_anchors(f"{user_text} {mary_text}"),
        ]
        episode["anchors"] = list(dict.fromkeys(merged))[:12]

    facts[_EPISODE_KEY] = _dump(episode)


def creativity_blocked(facts: Mapping[str, str]) -> bool:
    return str(facts.get(_BLOCKED_KEY, "false") or "false").lower() == "true"


def recall_episode(
    document: Mapping[str, Any],
    facts: dict[str, str],
    *,
    beat_id: str,
) -> str:
    """Recupera uma única cápsula depois que sua troca saiu do histórico recente."""

    policy = _policy(document)
    episode = _loads(facts.get(_EPISODE_KEY, ""))
    current_turn = int(facts.get(_TURN_KEY, "0") or 0)
    clean_beat_id = str(beat_id or "")
    if (
        not policy
        or not episode
        or episode.get("status") != "dormant"
        or current_turn < int(episode.get("eligible_after_turn", 0) or 0)
        or clean_beat_id == str(episode.get("source_beat_id", ""))
        or not _recall_allowed(policy, clean_beat_id)
    ):
        return ""

    episode["status"] = "consumed"
    episode["recalled_at_beat_id"] = clean_beat_id
    episode["recalled_at_turn"] = current_turn
    facts[_EPISODE_KEY] = _dump(episode)

    user_text = str(episode.get("latest_user_text") or episode.get("user_text") or "").strip()
    mary_text = str(episode.get("latest_mary_text") or episode.get("mary_text") or "").strip()
    return f'Usuário: "{user_text}" | Mary: "{mary_text}"'


__all__ = [
    "advance_episode_turn",
    "consolidate_bridge_episode",
    "creativity_blocked",
    "prepare_bridge_episode",
    "recall_episode",
]
