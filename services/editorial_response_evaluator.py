from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass
import json
import logging
import re
from typing import Any

from services.editorial_beat_context import BeatContext, render_beat_context


LOGGER = logging.getLogger("editorial.evaluation")
_LAST_EVALUATED_CANDIDATE: ContextVar[str] = ContextVar(
    "editorial_last_evaluated_candidate",
    default="",
)
_LAST_EVALUATION_CONTEXT: ContextVar[BeatContext | None] = ContextVar(
    "editorial_last_evaluation_context",
    default=None,
)
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
_VIOLATION_GUIDANCE = {
    "authored_thought_missing": "Inclua literalmente o pensamento autoral obrigatório dentro de um único bloco [PENSAMENTO].",
    "unexpected_thought": "Remova integralmente o pensamento: o beat atual não contém [PENSAMENTO] autoral.",
    "exact_speech_missing": "Inclua literalmente a fala autoral exata obrigatória na parte audível da resposta.",
    "forbidden_literal_text_repeated": "Remova o pensamento ou a fala autoral já consumida ou reservada a outro beat; produza apenas uma reação nova.",
    "bridge_question_created": "Remova a nova pergunta. A ponte deve reagir ao usuário sem criar assunto ou obrigação para o turno seguinte.",
    "invented_unconfirmed_detail": (
        "Não trate metáfora, flerte, humor, duplo sentido ou improviso plausível como fato novo. "
        "Corrija apenas contradições, ações presumidas do usuário ou avanço indevido do roteiro."
    ),
    "contradicted_confirmed_fact": "Reescreva sem contradizer nenhum fato confirmado.",
    "failed_required_outcome": "Realize todos os resultados obrigatórios de modo direto e breve.",
    "performed_forbidden_outcome": "Remova qualquer resultado listado como proibido.",
    "presumed_user_decision": "Mantenha a decisão do usuário explicitamente pendente.",
    "anticipated_future_beat": "Permaneça estritamente no beat atual, sem narrar o que acontecerá depois.",
    "closed_pending_route": "Não encerre uma interação cuja decisão ainda está pendente.",
    "failed_to_answer_user_question": "Responda diretamente à pergunta usando apenas fatos confirmados.",
    "failed_to_request_explicit_decision": "Ao final, peça uma decisão explícita sem pressão.",
    "treated_postpone_as_refusal": "Reconheça o adiamento sem convertê-lo em recusa.",
    "treated_question_as_acceptance": "Trate a pergunta como pedido de esclarecimento, não como aceite.",
    "character_voice_broken": "Preserve a voz natural da personagem.",
}


@dataclass(frozen=True, slots=True)
class ResponseEvaluation:
    valid: bool
    violations: tuple[str, ...] = ()


def _log_evaluation(stage: str, **payload: object) -> None:
    LOGGER.info(
        "editorial_evaluation %s",
        json.dumps({"stage": stage, **payload}, ensure_ascii=False, default=str),
    )


def _visible_dialogue(text: str) -> str:
    return _THOUGHT_PATTERN.sub("", str(text or "")).strip()


def _sentence_count(text: str) -> int:
    body = _visible_dialogue(text)
    if not body:
        return 0
    chunks = re.split(r"(?<=[.!?])(?:\s+|$)", body)
    return sum(1 for chunk in chunks if chunk.strip())


def _normalized(value: str) -> str:
    return " ".join(re.findall(r"\w+", str(value or "").casefold(), flags=re.UNICODE))


def _whitespace_normalized(value: str) -> str:
    return " ".join(str(value or "").split())


def _context_allows_violation(code: str, context: BeatContext | None) -> bool:
    if context is None:
        return True

    required = " ".join(context.required_outcomes).casefold()
    forbidden = " ".join(context.forbidden_outcomes).casefold()
    pending = context.transition_status == "decision_pending"

    if code == "invented_unconfirmed_detail":
        return False
    if code == "failed_to_answer_user_question":
        return context.user_intent == "question" or (
            "responder" in required and "pergunta" in required
        )
    if code == "failed_to_request_explicit_decision":
        return "decisão explícita" in required or "decisao explicita" in required
    if code == "treated_question_as_acceptance":
        return context.user_intent == "question"
    if code == "treated_postpone_as_refusal":
        return context.user_intent == "postpone"
    if code == "closed_pending_route":
        return pending
    if code == "presumed_user_decision":
        return pending or "presumir aceite" in forbidden or "presumir recusa" in forbidden
    return True


def evaluate_deterministic_response(
    response: str,
    context: BeatContext,
) -> ResponseEvaluation:
    text = str(response or "").strip()
    _LAST_EVALUATED_CANDIDATE.set(text)
    violations: list[str] = []

    if not text:
        result = ResponseEvaluation(False, ("empty_response",))
        _log_evaluation(
            "candidate_deterministic",
            candidate=text,
            valid=result.valid,
            violations=result.violations,
        )
        return result

    lowered = text.casefold()
    if any(marker.casefold() in lowered for marker in _TECHNICAL_MARKERS):
        violations.append("technical_marker_exposed")

    thought_matches = _THOUGHT_PATTERN.findall(text)
    if len(thought_matches) > 1:
        violations.append("multiple_thought_blocks")
    residual = _THOUGHT_PATTERN.sub("", text)
    if "[PENSAMENTO]" in residual.upper() or "[/PENSAMENTO]" in residual.upper():
        violations.append("malformed_thought_block")

    if context.authored_thought:
        required_thought = _whitespace_normalized(context.authored_thought)
        rendered_thoughts = " ".join(
            _whitespace_normalized(
                re.sub(
                    r"^\[PENSAMENTO\]|\[/PENSAMENTO\]$",
                    "",
                    item.strip(),
                    flags=re.IGNORECASE,
                )
            )
            for item in thought_matches
        )
        if required_thought not in rendered_thoughts:
            violations.append("authored_thought_missing")
    elif thought_matches:
        violations.append("unexpected_thought")

    visible = _visible_dialogue(text)
    if context.forbid_new_questions and "?" in visible:
        violations.append("bridge_question_created")
    if context.exact_speech and _whitespace_normalized(
        context.exact_speech
    ) not in _whitespace_normalized(visible):
        violations.append("exact_speech_missing")

    normalized_response = _whitespace_normalized(text)
    if any(
        _whitespace_normalized(fragment) in normalized_response
        for fragment in context.forbidden_literal_texts
        if _whitespace_normalized(fragment)
    ):
        violations.append("forbidden_literal_text_repeated")

    style_advisories: list[str] = []
    if context.max_sentences and _sentence_count(visible) > context.max_sentences:
        style_advisories.append("max_sentences_exceeded")
    if context.max_questions and visible.count("?") > context.max_questions:
        style_advisories.append("max_questions_exceeded")

    result = ResponseEvaluation(not violations, tuple(violations))
    _log_evaluation(
        "candidate_deterministic",
        candidate=text,
        valid=result.valid,
        violations=result.violations,
        style_advisories=style_advisories,
    )
    return result


def build_semantic_evaluation_prompt(context: BeatContext) -> str:
    _LAST_EVALUATION_CONTEXT.set(context)
    allowed = ", ".join(sorted(_ALLOWED_SEMANTIC_VIOLATIONS))
    return "\n".join(
        (
            "Você é um avaliador editorial consultivo. Não reescreva a resposta.",
            "Aponte riscos sem assumir autoridade para bloquear ou regenerar a fala.",
            "Faça uma auditoria factual: compare cada afirmação concreta da candidata com o conteúdo autorizado pelo contrato.",
            "Não rejeite metáfora, flerte, humor, duplo sentido, opinião, reação emocional ou improviso plausível apenas por não aparecer literalmente no roteiro.",
            "A infração invented_unconfirmed_detail é informativa e não bloqueia a resposta.",
            "Limites de frases e perguntas são orientação de estilo, não motivo autônomo para rejeição.",
            "Concentre os apontamentos em contradição de fatos confirmados, ação ou decisão presumida do usuário, resultado proibido e antecipação de beat.",
            "Para cada risco, cite em evidence o menor trecho literal da candidata que demonstra o problema.",
            "Só marque failed_to_answer_user_question quando a intenção detectada for question ou quando responder à pergunta estiver nos resultados obrigatórios.",
            "Só marque presumed_user_decision ou closed_pending_route quando a transição estiver pendente.",
            "Responda exclusivamente com um único objeto JSON válido, sem markdown e sem comentário:",
            '{"valid": false, "violations": [{"code": "anticipated_future_beat", "evidence": "trecho literal"}]}',
            "Quando não identificar riscos, responda: {\"valid\": true, \"violations\": []}",
            f"Identificadores permitidos em code: {allowed}",
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


def parse_semantic_evaluation(
    raw: str,
    *,
    candidate: str | None = None,
    context: BeatContext | None = None,
) -> ResponseEvaluation:
    text = str(raw or "").strip()
    effective_context = context or _LAST_EVALUATION_CONTEXT.get()
    effective_candidate = (
        str(candidate) if candidate is not None else _LAST_EVALUATED_CANDIDATE.get()
    )
    try:
        payload: Any = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        result = ResponseEvaluation(False, ("semantic_evaluator_invalid_json",))
        _log_evaluation("semantic_result", raw=text, valid=False, violations=result.violations)
        return result

    if not isinstance(payload, dict) or set(payload) != {"valid", "violations"}:
        result = ResponseEvaluation(False, ("semantic_evaluator_invalid_payload",))
        _log_evaluation("semantic_result", raw=text, valid=False, violations=result.violations)
        return result

    if not isinstance(payload.get("valid"), bool):
        result = ResponseEvaluation(False, ("semantic_evaluator_invalid_payload",))
        _log_evaluation("semantic_result", raw=text, valid=False, violations=result.violations)
        return result

    raw_violations = payload.get("violations")
    if not isinstance(raw_violations, list):
        result = ResponseEvaluation(False, ("semantic_evaluator_invalid_violations",))
        _log_evaluation("semantic_result", raw=text, valid=False, violations=result.violations)
        return result

    violations: list[str] = []
    discarded: list[dict[str, str]] = []
    for item in raw_violations:
        if isinstance(item, dict):
            code = str(item.get("code", "") or "").strip()
            evidence = str(item.get("evidence", "") or "").strip()
            if not code or not evidence:
                violations.append("semantic_evaluator_invalid_violations")
                continue
            if _normalized(evidence) not in _normalized(effective_candidate):
                violations.append("semantic_evaluator_invalid_violations")
                continue
        else:
            code = str(item).strip()
            evidence = ""

        if not code:
            continue
        if code not in _ALLOWED_SEMANTIC_VIOLATIONS:
            violations.append("semantic_evaluator_invalid_violations")
            continue
        if not _context_allows_violation(code, effective_context):
            discarded.append({"code": code, "reason": "non_blocking_or_incompatible_with_context"})
            continue
        violations.append(code)

    unique = tuple(dict.fromkeys(violations))
    declared_valid = payload["valid"] is True
    if declared_valid and unique:
        result = ResponseEvaluation(False, unique)
    elif not declared_valid and not unique:
        result = ResponseEvaluation(True, ())
    elif not declared_valid:
        result = ResponseEvaluation(False, unique)
    else:
        result = ResponseEvaluation(True, ())

    _log_evaluation(
        "semantic_result",
        raw=text,
        valid=result.valid,
        violations=result.violations,
        discarded=discarded,
    )
    return result


def merge_evaluations(*evaluations: ResponseEvaluation) -> ResponseEvaluation:
    """Mantém o determinístico soberano e registra os demais como consultivos.

    O primeiro resultado deve ser sempre o avaliador determinístico. Avaliações
    posteriores podem apontar riscos para diagnóstico, mas não rejeitam nem
    regeneram uma resposta por interpretação subjetiva isolada.
    """

    if not evaluations:
        result = ResponseEvaluation(True, ())
        _log_evaluation(
            "combined_result",
            valid=result.valid,
            violations=result.violations,
            semantic_advisories=(),
        )
        return result

    authoritative = evaluations[0]
    advisories = tuple(
        dict.fromkeys(
            violation
            for evaluation in evaluations[1:]
            for violation in evaluation.violations
        )
    )
    result = ResponseEvaluation(
        authoritative.valid and not authoritative.violations,
        authoritative.violations,
    )
    _log_evaluation(
        "combined_result",
        valid=result.valid,
        violations=result.violations,
        semantic_advisories=advisories,
        semantic_authority="consultive",
    )
    return result


def build_regeneration_prompt(
    *,
    base_prompt: str,
    violations: tuple[str, ...],
    rejected_candidate: str = "",
) -> str:
    unique = tuple(dict.fromkeys(str(item).strip() for item in violations if str(item).strip()))
    guidance = [
        _VIOLATION_GUIDANCE.get(item, f"Corrija estritamente a violação: {item}.")
        for item in unique
    ]
    reasons = "\n".join(f"- {item}" for item in unique) or "- resposta_rejeitada"
    instructions = "\n".join(f"- {item}" for item in guidance)
    rejected = str(rejected_candidate or _LAST_EVALUATED_CANDIDATE.get() or "").strip()
    rejected_block = (
        "\nRESPOSTA REJEITADA — use apenas para identificar e remover os erros; não a parafraseie:\n"
        f"{rejected}\n"
        if rejected
        else ""
    )
    _LAST_EVALUATED_CANDIDATE.set("")
    return (
        f"{str(base_prompt or '').strip()}\n\n"
        "REGENERAÇÃO EDITORIAL CONTROLADA:\n"
        "A resposta anterior foi rejeitada. Reconstrua a fala do zero, em forma mínima e natural.\n"
        "Use somente os fatos confirmados e os resultados obrigatórios do contrato; não acrescente fatos não autorizados.\n"
        "Preserve metáforas, flerte, humor, duplo sentido e reações naturais que não contradigam o roteiro.\n"
        "Remova somente contradições, ações ou decisões presumidas do usuário, resultados proibidos e antecipações de beat.\n"
        "Quando faltar um fato necessário, formule de modo neutro em vez de completar a lacuna.\n"
        "Não comente a avaliação e não repita nenhum detalhe realmente rejeitado.\n"
        f"{rejected_block}"
        "MOTIVOS OBJETIVOS DA REJEIÇÃO:\n"
        f"{reasons}\n"
        "INSTRUÇÕES DE CORREÇÃO:\n"
        f"{instructions}"
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
