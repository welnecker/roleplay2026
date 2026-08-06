from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


_THIRD_PERSON_THOUGHT = re.compile(
    r"\b(?:mary|ela)\s+(?:pensa|sente|percebe|imagina|se pergunta|teme|deseja)\b",
    re.IGNORECASE,
)
_FIRST_PERSON_THOUGHT = re.compile(
    r"\b(?:eu|me|meu|minha|comigo|mim)\b",
    re.IGNORECASE,
)
_GENERIC_OPENERS = (
    "entendo",
    "compreendo",
    "certo",
    "ok",
    "está bem",
    "tudo bem",
)
_DEFAULT_THOUGHT_MARKERS = (
    ("[PENSAMENTO]", "[/PENSAMENTO]"),
    ("<thought>", "</thought>"),
)


@dataclass(frozen=True, slots=True)
class DepthPerceptionReport:
    score: int
    beat_centrality: bool
    user_specificity: bool
    emotional_embodiment: bool
    concise_completion: bool
    first_person_thought: bool
    third_person_thought_violation: bool
    bureaucratic_delivery: bool
    reasons: tuple[str, ...]

    @property
    def perceived_depth(self) -> str:
        if self.score >= 8:
            return "deep"
        if self.score >= 5:
            return "adequate"
        return "shallow"


def assess_depth_perception(
    response: str,
    *,
    beat_terms: Iterable[str],
    user_terms: Iterable[str] = (),
    emotional_terms: Iterable[str] = (),
    max_sentences: int = 3,
    thought_markers: tuple[str, str] | tuple[tuple[str, str], ...] | None = None,
) -> DepthPerceptionReport:
    """Avalia sinais observáveis de profundidade sem depender de um LLM juiz."""

    text = str(response or "").strip()
    normalized = text.casefold()
    reasons: list[str] = []

    beat_hits = _term_hits(normalized, beat_terms)
    beat_centrality = beat_hits > 0
    if not beat_centrality:
        reasons.append("o núcleo semântico do beat não aparece")

    user_terms_clean = tuple(_clean_terms(user_terms))
    user_specificity = not user_terms_clean or _term_hits(normalized, user_terms_clean) > 0
    if not user_specificity:
        reasons.append("a resposta não reage a nenhum detalhe específico do usuário")

    emotional_terms_clean = tuple(_clean_terms(emotional_terms))
    emotional_embodiment = not emotional_terms_clean or _term_hits(normalized, emotional_terms_clean) > 0
    if not emotional_embodiment:
        reasons.append("a pressão emocional não altera a forma visível da fala")

    sentence_count = _sentence_count(text)
    concise_completion = bool(text) and sentence_count <= max(1, int(max_sentences))
    if not concise_completion:
        reasons.append("a resposta ultrapassa o orçamento de frases")

    thought = _extract_thought(text, thought_markers)
    third_person_violation = bool(thought and _THIRD_PERSON_THOUGHT.search(thought))
    first_person_thought = not thought or bool(_FIRST_PERSON_THOUGHT.search(thought))
    if third_person_violation:
        reasons.append("o pensamento interno usa narração psicológica em terceira pessoa")
    elif not first_person_thought:
        reasons.append("o pensamento interno não está formulado na voz íntima de Mary")

    bureaucratic_delivery = _looks_bureaucratic(
        normalized,
        beat_hits=beat_hits,
        user_specificity=user_specificity,
        emotional_embodiment=emotional_embodiment,
    )
    if bureaucratic_delivery:
        reasons.append("o beat é entregue como obrigação funcional, sem integração orgânica")

    score = 0
    score += 3 if beat_centrality else 0
    score += 2 if user_specificity else 0
    score += 2 if emotional_embodiment else 0
    score += 1 if concise_completion else 0
    score += 1 if first_person_thought else 0
    score += 1 if not third_person_violation else 0
    score -= 2 if bureaucratic_delivery else 0
    score = max(0, min(10, score))

    return DepthPerceptionReport(
        score=score,
        beat_centrality=beat_centrality,
        user_specificity=user_specificity,
        emotional_embodiment=emotional_embodiment,
        concise_completion=concise_completion,
        first_person_thought=first_person_thought,
        third_person_thought_violation=third_person_violation,
        bureaucratic_delivery=bureaucratic_delivery,
        reasons=tuple(reasons),
    )


def _clean_terms(values: Iterable[str]) -> list[str]:
    return [str(value).strip().casefold() for value in values if str(value).strip()]


def _term_hits(text: str, values: Iterable[str]) -> int:
    return sum(1 for item in _clean_terms(values) if item in text)


def _sentence_count(text: str) -> int:
    chunks = [item.strip() for item in re.split(r"(?<=[.!?])\s+|\n+", text) if item.strip()]
    return len(chunks)


def _marker_pairs(
    markers: tuple[str, str] | tuple[tuple[str, str], ...] | None,
) -> tuple[tuple[str, str], ...]:
    if markers is None:
        return _DEFAULT_THOUGHT_MARKERS
    if len(markers) == 2 and all(isinstance(item, str) for item in markers):
        start, end = markers
        return ((str(start), str(end)), *_DEFAULT_THOUGHT_MARKERS)
    pairs = tuple(
        (str(item[0]), str(item[1]))
        for item in markers
        if isinstance(item, tuple) and len(item) == 2
    )
    return tuple(dict.fromkeys((*pairs, *_DEFAULT_THOUGHT_MARKERS)))


def _extract_thought(
    text: str,
    markers: tuple[str, str] | tuple[tuple[str, str], ...] | None,
) -> str:
    for start, end in _marker_pairs(markers):
        if start and end and start in text and end in text:
            return text.split(start, 1)[1].split(end, 1)[0].strip()
    return ""


def _looks_bureaucratic(
    normalized: str,
    *,
    beat_hits: int,
    user_specificity: bool,
    emotional_embodiment: bool,
) -> bool:
    clean = normalized.strip(" \n\t—-.:;!?\"")
    starts_generic = any(clean.startswith(item) for item in _GENERIC_OPENERS)
    minimal = len(clean.split()) <= 12
    return bool(
        beat_hits
        and minimal
        and (starts_generic or not user_specificity)
        and not emotional_embodiment
    )


__all__ = ["DepthPerceptionReport", "assess_depth_perception"]
