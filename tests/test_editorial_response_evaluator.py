from __future__ import annotations

from services.editorial_beat_context import BeatContext, render_beat_context
from services.editorial_response_evaluator import (
    build_regeneration_prompt,
    build_semantic_evaluation_prompt,
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
        "allowed_topics": ("o pedido para esperar", "a ajuda com as compras"),
        "confirmed_facts": (
            "Mary está no caixa com compras",
            "local da cena: supermercado_caixa",
        ),
        "unknown_facts": (
            "o lugar exato onde o usuário deve esperar",
            "o peso das compras",
            "roupas e calçados",
        ),
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


def test_limites_de_estilo_nao_bloqueiam_resposta_narrativamente_valida() -> None:
    result = evaluate_deterministic_response(
        "Primeira. Segunda? Terceira? Quarta.",
        _context(max_sentences=3, max_questions=1),
    )

    assert result.valid is True
    assert result.violations == ()


def test_contexto_separa_fatos_desconhecidos_e_assuntos() -> None:
    rendered = render_beat_context(_context())

    assert "FATOS CONFIRMADOS" in rendered
    assert "Mary está no caixa com compras" in rendered
    assert "FATOS DESCONHECIDOS" in rendered
    assert "o lugar exato onde o usuário deve esperar" in rendered
    assert "ASSUNTOS PERMITIDOS" in rendered
    assert "não podem ser concretizados" in rendered


def test_prompt_semantico_preserva_linguagem_viva_e_travas_estruturais() -> None:
    prompt = build_semantic_evaluation_prompt(_context())

    assert "compare cada afirmação concreta" in prompt
    assert "metáfora, flerte, humor, duplo sentido" in prompt
    assert "invented_unconfirmed_detail é informativa" in prompt
    assert "Limites de frases e perguntas são orientação de estilo" in prompt
    assert "contradição de fatos confirmados" in prompt
    assert "um único objeto JSON" in prompt


def test_avaliacao_semantica_exige_json_puro_e_valido() -> None:
    prose = parse_semantic_evaluation("A resposta está boa.")
    fenced = parse_semantic_evaluation('```json\n{"valid": true, "violations": []}\n```')
    valid = parse_semantic_evaluation('{"valid": true, "violations": []}')

    assert prose.valid is False
    assert prose.violations == ("semantic_evaluator_invalid_json",)
    assert fenced.valid is False
    assert fenced.violations == ("semantic_evaluator_invalid_json",)
    assert valid.valid is True


def test_avaliacao_semantica_rejeita_identificador_fora_do_contrato() -> None:
    result = parse_semantic_evaluation(
        '{"valid": false, "violations": ["qualquer_texto_livre"]}'
    )

    assert result.valid is False
    assert result.violations == ("semantic_evaluator_invalid_violations",)


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
        violations=("failed_to_request_explicit_decision", "anticipated_future_beat"),
    )

    assert "Contrato base." in prompt
    assert "failed_to_request_explicit_decision" in prompt
    assert "anticipated_future_beat" in prompt
    assert "não acrescente fatos" in prompt
    assert "Preserve metáforas, flerte, humor, duplo sentido" in prompt
