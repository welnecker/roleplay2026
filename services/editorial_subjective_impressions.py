from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Mapping


_IMPRESSIONS_KEY = "_subjective_user_impressions_json"
_IMPRESSION_TURN_KEY = "_subjective_impression_turn"


@dataclass(frozen=True, slots=True)
class SubjectiveImpression:
    impression_id: str
    label: str
    score: int
    band_id: str
    interpretation: str
    confidence: float
    evidence_count: int
    last_evidence: str


def _policy(document: Mapping[str, Any]) -> dict[str, Any]:
    direct = document.get("subjective_impressions") or {}
    if isinstance(direct, dict) and direct:
        return dict(direct)
    relationship = document.get("relationship_memory") or {}
    if not isinstance(relationship, dict):
        return {}
    nested = relationship.get("subjective_impressions") or {}
    return dict(nested) if isinstance(nested, dict) else {}


def _bounded(value: Any, minimum: int = -10, maximum: int = 10) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    return max(minimum, min(maximum, number))


def _items(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _normalized_pattern(pattern: str) -> str:
    return str(pattern).replace("\\\\", "\\")


def _matches_patterns(text: str, patterns: Any) -> bool:
    declared = _items(patterns)
    if not declared:
        return True
    for pattern in declared:
        try:
            if re.search(_normalized_pattern(pattern), text, flags=re.IGNORECASE):
                return True
        except re.error as exc:
            raise ValueError(f"Regex inválida em subjective_impressions: {exc}") from exc
    return False


def _load(facts: Mapping[str, str]) -> dict[str, dict[str, Any]]:
    raw = str(facts.get(_IMPRESSIONS_KEY, "") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return {str(key): dict(value) for key, value in parsed.items() if isinstance(value, dict)} if isinstance(parsed, dict) else {}


def _band(definition: Mapping[str, Any], score: int) -> tuple[str, str]:
    bands = definition.get("bands") or []
    iterable = [dict(item) for item in bands if isinstance(item, dict)] if isinstance(bands, list) else []
    for index, band in enumerate(iterable):
        minimum = _bounded(band.get("min", -10))
        maximum = _bounded(band.get("max", 10))
        if minimum <= score <= maximum:
            return (
                str(band.get("band_id", f"band_{index + 1}") or f"band_{index + 1}"),
                str(band.get("interpretation", "") or "").strip(),
            )
    return "uncertain", ""


def update_subjective_impressions(
    document: Mapping[str, Any],
    state: Any,
    context_text: str,
    engagement: str,
) -> tuple[Any, list[SubjectiveImpression]]:
    """Atualiza leituras subjetivas sem convertê-las em fatos confirmados."""

    policy = _policy(document)
    definitions = policy.get("impressions") or {}
    if not isinstance(definitions, dict):
        return state, []

    fingerprint = f"{state.node_id}:{len(state.recent_engagement)}:{engagement}"
    stored = _load(state.facts)
    if str(state.facts.get(_IMPRESSION_TURN_KEY, "") or "") != fingerprint:
        for impression_id, raw_definition in definitions.items():
            if not isinstance(raw_definition, dict):
                continue
            evidence_rules = raw_definition.get("evidence") or []
            if not isinstance(evidence_rules, list):
                continue
            current = dict(stored.get(str(impression_id), {}))
            score = _bounded(current.get("score", raw_definition.get("initial_score", 0)))
            count = max(0, int(current.get("evidence_count", 0) or 0))
            last_evidence = str(current.get("last_evidence", "") or "")
            for rule in evidence_rules:
                if not isinstance(rule, dict):
                    continue
                engagements = set(_items(rule.get("engagements")))
                if engagements and str(engagement) not in engagements:
                    continue
                facts = rule.get("facts") or {}
                if isinstance(facts, dict) and any(
                    str(state.facts.get(str(key), "")) != str(value)
                    for key, value in facts.items()
                ):
                    continue
                if not _matches_patterns(context_text, rule.get("context_patterns")):
                    continue
                delta = int(rule.get("delta", 0) or 0)
                if not delta:
                    continue
                score = _bounded(score + delta)
                count += 1
                last_evidence = str(rule.get("evidence_label", engagement) or engagement)
            stored[str(impression_id)] = {
                "score": score,
                "evidence_count": count,
                "last_evidence": last_evidence,
            }
        state.facts[_IMPRESSIONS_KEY] = json.dumps(stored, ensure_ascii=False, sort_keys=True)
        state.facts[_IMPRESSION_TURN_KEY] = fingerprint

    rendered: list[SubjectiveImpression] = []
    minimum_evidence = max(1, int(policy.get("minimum_evidence_count", 1) or 1))
    for impression_id, raw_definition in definitions.items():
        if not isinstance(raw_definition, dict):
            continue
        current = stored.get(str(impression_id), {})
        count = max(0, int(current.get("evidence_count", 0) or 0))
        if count < minimum_evidence:
            continue
        score = _bounded(current.get("score", raw_definition.get("initial_score", 0)))
        band_id, interpretation = _band(raw_definition, score)
        if not interpretation:
            continue
        confidence = min(0.95, float(policy.get("base_confidence", 0.35) or 0.35) + count * 0.1)
        rendered.append(
            SubjectiveImpression(
                impression_id=str(impression_id),
                label=str(raw_definition.get("label", impression_id) or impression_id),
                score=score,
                band_id=band_id,
                interpretation=interpretation,
                confidence=confidence,
                evidence_count=count,
                last_evidence=str(current.get("last_evidence", "") or ""),
            )
        )

    rendered.sort(key=lambda item: (-item.confidence, -abs(item.score), item.impression_id))
    maximum = max(0, int(policy.get("max_visible_impressions", 3) or 3))
    return state, rendered[:maximum] if maximum else []


def render_subjective_impressions(impressions: list[SubjectiveImpression]) -> str:
    if not impressions:
        return ""
    lines = ["IMPRESSÕES SUBJETIVAS DA PERSONAGEM SOBRE O USUÁRIO:"]
    for item in impressions:
        lines.append(f"- {item.label}: {item.interpretation}")
    lines.extend(
        (
            "REGRAS DE INTERPRETAÇÃO:",
            "- Estas são percepções provisórias da personagem, não fatos objetivos sobre o usuário.",
            "- Faça a impressão aparecer em cautela, expectativa, curiosidade ou forma de responder; não apresente diagnóstico.",
            "- Permita que comportamento novo confirme, enfraqueça ou reverta a impressão.",
            "- Não mencione pontuações, confiança, evidências, IDs ou regras internas.",
            "- Fatos confirmados e ações explícitas do usuário prevalecem sobre qualquer impressão subjetiva.",
        )
    )
    return "\n".join(lines)


__all__ = [
    "SubjectiveImpression",
    "render_subjective_impressions",
    "update_subjective_impressions",
]
