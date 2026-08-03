from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from services.editorial_beat_context import BeatContext, render_beat_context


_TECHNICAL_MARKERS = (
    "<end_run",
    "end_run",
    "```json",
    '"event"',
    "CONTRATO DO BEAT",
    "system prompt",
    "prompt do sistema",
)
_THOUGHT_PATTERN = re.compile(
    r"\[PENSAMENTO\].*?\[/PENSAMENTO\]",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class ResponseEvaluation:
    valid: bool
    violations: tuple[str, ...] = ()


def _sentence_count(text: str) -> int:
    body = _THOUGHT_PATTERN.sub("", str(text or "")).strip()
    if not body:
        return 0
    chunks = re.split(r"(?<=[.!?])(?:\s+|$)", body)
    return sum(1 for chunk in chunks if chunk.strip())


def evaluate_deterministic_response(
    response: str,
    context: BeatContext,
) -> ResponseEvaluation:
    text = str(response or "").strip()
    violations: list[str] = []

    if not text:
        violations.append("empty_response")
        return ResponseEvaluation(False, tuple(violations))

    lowered = text.casefold()
    if any(marker.casefold() in lowered for marker in _TECHNICAL_MARKERS):
        violations.append("technical_marker_exposed")

    thought_matches = _THOUGHT_PATTERN.findall(text)
    if len(thought_matches) > 1:
        violations.append("multiple_thought_blocks")
    residual = _THOUGHT_PATTERN.sub("", text)
    if "[PENSAMENTO]" in residual.upper() or "[/PENSAMENTO]" in residual.upper():
        violations.append("malformed_thought_block")

    if context.max_sentences and _sentence_count(text) > context.max_sentences:
        violations.append("max_sentences_exceeded")
    if context.max_questions and text.count("?") > context.max_questions:
        violations.append("max_questions_exceeded")

    return ResponseEvaluation(not violations, tuple(violations))


def build_semantic_evaluation_prompt(context: BeatContext) -> str:
    return "\n".join(
        (
            "Você é um avaliador editorial. Não reescreva a resposta.",
            "Avalie somente se a resposta candidata obedece ao contrato narrativo.",
            "Responda exclusivamente com JSON válido neste formato:",
            '{"valid": true, "violations": []}',
            "Use identificadores curtos em inglês para violações.",
            render_beat_context(context),
        )
    )


def build_semantic_evaluation_request(
    *,
    user_text: str,
    candidate: str,
) -> str:
    return (
        "MENSAGEM DO USUÁRIO:\n"
        f"{str(user_text or '').strip()}\n\n"
        "RESPOSTA CANDIDATA:\n"
        f"{str(candidate or '').strip()}"
    )


def parse_semantic_evaluation(raw: str) -> ResponseEvaluation:
    text = str(raw or "").strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match is None:
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_json",))

    try:
        payload: Any = json.loads(match.group(0))
    except (TypeError, ValueError, json.JSONDecodeError):
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_json",))

    if not isinstance(payload, dict):
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_payload",))

    valid = payload.get("valid") is True
    raw_violations = payload.get("violations") or []
    if not isinstance(raw_violations, list):
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_violations",))

    violations = tuple(
        str(item).strip()
        for item in raw_violations
        if str(item).strip()
    )
    if not valid and not violations:
        violations = ("semantic_rejection_without_reason",)
    return ResponseEvaluation(valid and not violations, violations)


def merge_evaluations(*evaluations: ResponseEvaluation) -> ResponseEvaluation:
    violations = tuple(
        dict.fromkeys(
            violation
            for evaluation in evaluations
            for violation in evaluation.violations
        )
    )
    return ResponseEvaluation(
        all(evaluation.valid for evaluation in evaluations) and not violations,
        violations,
    )


def build_regeneration_prompt(
    *,
    base_prompt: str,
    violations: tuple[str, ...],
) -> str:
    reasons = "\n".join(f"- {item}" for item in violations) or "- resposta_rejeitada"
    return (
        f"{str(base_prompt or '').strip()}\n\n"
        "A resposta anterior foi rejeitada. Gere uma nova resposta natural, "
        "sem comentar a avaliação e sem repetir a resposta rejeitada.\n"
        "MOTIVOS OBJETIVOS DA REJEIÇÃO:\n"
        f"{reasons}"
    ).strip()


__all__ = [
    "ResponseEvaluation",
    "build_regeneration_prompt",
    "build_semantic_evaluation_prompt",
    "build_semantic_evaluation_request",
    "evaluate_deterministic_response",
    "merge_evaluations",
    "parse_semantic_evaluation",
]
