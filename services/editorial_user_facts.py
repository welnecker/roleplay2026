from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from typing import Any, Mapping


_FACT_RECORDS_KEY = "_structured_user_facts_json"
_FACT_HISTORY_KEY = "_structured_user_fact_history_json"


@dataclass(frozen=True, slots=True)
class UserFactRecord:
    fact_id: str
    value: str
    confidence: float
    source: str
    evidence: str
    status: str = "active"
    supersedes: str = ""


def _string_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "").strip()


def _load_records(facts: Mapping[str, str]) -> dict[str, UserFactRecord]:
    raw = str(facts.get(_FACT_RECORDS_KEY, "") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    records: dict[str, UserFactRecord] = {}
    for fact_id, item in parsed.items():
        if not isinstance(item, dict):
            continue
        records[str(fact_id)] = UserFactRecord(
            fact_id=str(fact_id),
            value=_string_value(item.get("value", "")),
            confidence=max(0.0, min(1.0, float(item.get("confidence", 0.0) or 0.0))),
            source=str(item.get("source", "") or ""),
            evidence=str(item.get("evidence", "") or ""),
            status=str(item.get("status", "active") or "active"),
            supersedes=_string_value(item.get("supersedes", "")),
        )
    return records


def _load_history(facts: Mapping[str, str]) -> list[dict[str, Any]]:
    raw = str(facts.get(_FACT_HISTORY_KEY, "") or "").strip()
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [dict(item) for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _fact_policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("user_fact_schema") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("user_fact_schema") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _normalized_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def _match_declared_value(
    text: str,
    fact_id: str,
    definition: Mapping[str, Any],
) -> UserFactRecord | None:
    extractors = definition.get("extractors") or []
    if not isinstance(extractors, list):
        return None
    for index, extractor in enumerate(extractors):
        if not isinstance(extractor, dict):
            continue
        pattern = str(extractor.get("pattern", "") or "").strip()
        value = _string_value(extractor.get("value", ""))
        if not pattern or not value:
            continue
        try:
            match = re.search(pattern, text, flags=re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"Regex inválida em user_fact_schema.{fact_id}: {exc}") from exc
        if match is None:
            continue
        confidence = max(0.0, min(1.0, float(extractor.get("confidence", 1.0) or 1.0)))
        source = str(extractor.get("source", f"declared_pattern_{index + 1}") or f"declared_pattern_{index + 1}")
        return UserFactRecord(
            fact_id=fact_id,
            value=value,
            confidence=confidence,
            source=source,
            evidence=match.group(0).strip(),
        )
    return None


def _should_replace(
    current: UserFactRecord | None,
    incoming: UserFactRecord,
    definition: Mapping[str, Any],
) -> bool:
    if current is None or current.status != "active":
        return True
    if current.value == incoming.value:
        return incoming.confidence >= current.confidence
    policy = str(definition.get("update_policy", "replace_on_equal_or_higher_confidence") or "replace_on_equal_or_higher_confidence")
    if policy == "never_replace":
        return False
    if policy == "replace_on_explicit":
        threshold = float(definition.get("explicit_confidence", 0.9) or 0.9)
        return incoming.confidence >= threshold
    return incoming.confidence >= current.confidence


def extract_declared_user_facts(
    document: Mapping[str, Any],
    user_text: str,
    known_facts: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Extrai fatos somente de padrões declarados pelo card."""

    facts = {str(key): str(value) for key, value in dict(known_facts or {}).items()}
    text = _normalized_text(user_text)
    policy = _fact_policy(document)
    definitions = policy.get("facts") or {}
    if not text or not isinstance(definitions, dict):
        return facts

    records = _load_records(facts)
    history = _load_history(facts)
    groups: dict[str, str] = {}
    for existing_id, definition in definitions.items():
        if isinstance(definition, dict):
            group = str(definition.get("exclusive_group", "") or "").strip()
            if group and existing_id in records and records[existing_id].status == "active":
                groups[group] = str(existing_id)

    changed = False
    for raw_fact_id, raw_definition in definitions.items():
        fact_id = str(raw_fact_id).strip()
        if not fact_id or not isinstance(raw_definition, dict):
            continue
        incoming = _match_declared_value(text, fact_id, raw_definition)
        if incoming is None:
            continue
        minimum = float(raw_definition.get("minimum_confidence", 0.8) or 0.8)
        if incoming.confidence < minimum:
            continue
        current = records.get(fact_id)
        if not _should_replace(current, incoming, raw_definition):
            continue

        group = str(raw_definition.get("exclusive_group", "") or "").strip()
        superseded_id = groups.get(group, "") if group else ""
        if superseded_id and superseded_id != fact_id and superseded_id in records:
            previous = records[superseded_id]
            records[superseded_id] = UserFactRecord(**{**asdict(previous), "status": "superseded"})
            history.append({**asdict(previous), "status": "superseded_by", "superseded_by": fact_id})
            facts.pop(superseded_id, None)

        if current is not None and current.value != incoming.value:
            history.append({**asdict(current), "status": "replaced", "replaced_by_value": incoming.value})
            incoming = UserFactRecord(**{**asdict(incoming), "supersedes": current.value})

        records[fact_id] = incoming
        facts[fact_id] = incoming.value
        if group:
            groups[group] = fact_id
        changed = True

    if changed:
        facts[_FACT_RECORDS_KEY] = _dump({key: asdict(value) for key, value in records.items()})
        facts[_FACT_HISTORY_KEY] = _dump(history[-50:])
    return facts


def structured_user_facts(facts: Mapping[str, str]) -> dict[str, UserFactRecord]:
    return {
        fact_id: record
        for fact_id, record in _load_records(facts).items()
        if record.status == "active"
    }


def render_confirmed_user_facts(facts: Mapping[str, str]) -> str:
    records = structured_user_facts(facts)
    if not records:
        return ""
    lines = ["FATOS CONFIRMADOS SOBRE O USUÁRIO:"]
    lines.extend(f"- {record.fact_id}: {record.value}" for record in records.values())
    lines.extend(
        (
            "REGRAS DE USO:",
            "- Trate apenas estes valores como fatos confirmados.",
            "- Não transforme impressão, hipótese, brincadeira ou ausência de resposta em fato.",
            "- Quando um valor tiver sido substituído, use somente o valor ativo mais recente.",
        )
    )
    return "\n".join(lines)


__all__ = [
    "UserFactRecord",
    "extract_declared_user_facts",
    "render_confirmed_user_facts",
    "structured_user_facts",
]
