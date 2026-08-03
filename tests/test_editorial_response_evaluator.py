from __future__ import annotations

from services.editorial_beat_context import BeatContext
from services.editorial_response_evaluator import (
    build_regeneration_prompt,
    evaluate_deterministic_response,
    merge_evaluations,
    parse_semantic_evaluation,
)


def _context(**overrides):
    values = {
        "source_beat_id": "origem",
        "target_beat_id": "alvo",
        "objective": "manter a decisão pendente",
        "canonical_line": "Você consegue me esperar?",
        "dramatic_direction": "Sem pressão.",
        "user_intent": "postpone",
        "transition_status": "decision_pending",
        "required_outcomes": ("reconhecer o adiamento", "pedir decisão explícita"),
        "forbidden_outcomes": ("encerrar o encontro", "presumir recusa"),
        "relevant_facts": {"help_to_car": "pending"},
        "max_sentences": 3,
        "max_questions": 1,
        "response_boundary": "",
    }
    values.update(overrides)
    return BeatContext(**values)


def test_validacao_deterministica_rejeita_resposta_vazia() -> None:
    result = evaluate_deterministic_response("", _context())

    assert result.valid is False
    assert result.violations == ("empty_response",)


def test_validacao_deterministica_aplica_limites_do_beat() -> None:
    result = evaluate_deterministic_response(
        "Primeira. Segunda? Terceira? Quarta.",
        _context(max_sentences=3, max_questions=1),
    )

    assert result.valid is False
    assert "max_sentences_exceeded" in result.violations
    assert "max_questions_exceeded" in result.violations


def test_avaliacao_semantica_exige_json_valido() -> None:
    invalid = parse_semantic_evaluation("A resposta está boa.")
    valid = parse_semantic_evaluation('{"valid": true, "violations": []}')

    assert invalid.valid is False
    assert invalid.violations == ("semantic_evaluator_invalid_json",)
    assert valid.valid is True


def test_merge_mantem_runtime_soberano() -> None:
    deterministic = evaluate_deterministic_response("Tudo bem. Você pode me confirmar?", _context())
    semantic = parse_semantic_evaluation(
        '{"valid": false, "violations": ["treated_postpone_as_refusal"]}'
    )

    merged = merge_evaluations(deterministic, semantic)

    assert merged.valid is False
    assert "treated_postpone_as_refusal" in merged.violations


def test_regeneracao_recebe_motivos_objetivos() -> None:
    prompt = build_regeneration_prompt(
        base_prompt="Contrato base.",
        violations=("failed_to_request_confirmation", "anticipated_future_beat"),
    )

    assert "Contrato base." in prompt
    assert "failed_to_request_confirmation" in prompt
    assert "anticipated_future_beat" in prompt
    assert "sem comentar a avaliação" in prompt
