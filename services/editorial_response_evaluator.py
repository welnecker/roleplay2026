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
_ALLOWED_SEMANTIC_VIOLATIONS = frozenset(
    {
        "invented_unconfirmed_detail",
        "contradicted_confirmed_fact",
        "failed_required_outcome",
        "performed_forbidden_outcome",
        "presumed_user_decision",
        "anticipated_future_beat",
        "closed_pending_route",
        "failed_to_answer_user_question",
        "failed_to_request_explicit_decision",
        "treated_postpone_as_refusal",
        "treated_question_as_acceptance",
        "character_voice_broken",
        "semantic_evaluator_invalid_json",
        "semantic_evaluator_invalid_payload",
        "semantic_evaluator_invalid_violations",
        "semantic_rejection_without_reason",
    }
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
        return ResponseEvaluation(False, ("empty_response",))

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
    allowed = ", ".join(sorted(_ALLOWED_SEMANTIC_VIOLATIONS))
    return "\n".join(
        (
            "Você é um avaliador editorial estrito. Não reescreva a resposta.",
            "Avalie somente se a candidata obedece integralmente ao contrato narrativo.",
            "O escopo factual não autoriza detalhes concretos adicionais. Um detalhe plausível, engraçado ou coerente continua sendo invenção quando não está confirmado.",
            "Rejeite causas, quantidades, objetos, roupas, calçados, riscos, distâncias, condições físicas, urgências ou localizações específicas não declaradas.",
            "Rejeite também qualquer resposta que presuma a decisão do usuário, encerre uma rota pendente, antecipe o beat seguinte ou deixe de cumprir um resultado obrigatório.",
            "Responda exclusivamente com um único objeto JSON válido, sem markdown e sem comentário:",
            '{"valid": true, "violations": []}',
            f"Identificadores permitidos em violations: {allowed}",
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
    try:
        payload: Any = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_json",))

    if not isinstance(payload, dict) or set(payload) != {"valid", "violations"}:
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_payload",))

    if not isinstance(payload.get("valid"), bool):
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_payload",))

    raw_violations = payload.get("violations")
    if not isinstance(raw_violations, list):
        return ResponseEvaluation(False, ("semantic_evaluator_invalid_violations",))

    violations: list[str] = []
    for item in raw_violations:
        value = str(item).strip()
        if not value:
            continue
        violations.append(
            value if value in _ALLOWED_SEMANTIC_VIOLATIONS else "semantic_evaluator_invalid_violations"
        )

    unique = tuple(dict.fromkeys(violations))
    valid = payload["valid"] is True
    if not valid and not unique:
        unique = ("semantic_rejection_without_reason",)
    if valid and unique:
        return ResponseEvaluation(False, unique)
    return ResponseEvaluation(valid, unique)


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
        "A resposta anterior foi rejeitada. Gere uma nova resposta inteiramente nova e natural. "
        "Não comente a avaliação, não repita trechos rejeitados e não acrescente fatos para tornar a fala mais interessante.\n"
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
