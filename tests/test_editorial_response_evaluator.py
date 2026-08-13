from __future__ import annotations

from services.editorial_beat_context import BeatContext, render_beat_context
from services.editorial_response_evaluator import (
    ResponseEvaluation,
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


def test_texto_autoral_obrigatorio_e_validado_literalmente() -> None:
    context = _context(
        authored_thought="Quero sentir essa aproximação.",
        exact_speech="Pode chegar mais perto, Vini.",
    )

    extended = evaluate_deterministic_response(
        "[PENSAMENTO]\nQuero sentir essa aproximação.\n[/PENSAMENTO]\n\n"
        "Pode chegar mais perto, Vini. Estou esperando.",
        context,
    )
    valid = evaluate_deterministic_response(
        "[PENSAMENTO]\nQuero sentir essa aproximação.\n[/PENSAMENTO]\n\n"
        "Pode chegar mais perto, Vini.",
        context,
    )
    changed = evaluate_deterministic_response(
        "[PENSAMENTO]\nEstou curiosa com essa aproximação.\n[/PENSAMENTO]\n\n"
        "Chegue perto de mim, Vini.",
        context,
    )

    assert valid.valid is True
    assert extended.valid is False
    assert extended.violations == ("exact_speech_extension",)
    assert changed.valid is False
    assert changed.violations == (
        "authored_thought_missing",
        "exact_speech_missing",
    )


def test_economia_estrita_rejeita_complemento_e_frases_excedentes() -> None:
    context = _context(
        canonical_line="Poxa... você me salvou.",
        max_sentences=2,
        strict_response_economy=True,
        max_extra_words=6,
    )

    concise = evaluate_deterministic_response(
        "Poxa... você me salvou, Janio.",
        context,
    )
    padded = evaluate_deterministic_response(
        "Poxa... você me salvou, Janio. Eu já estava desanimada. Agora meu dia começou de verdade com você.",
        context,
    )

    assert concise.valid is True
    assert padded.valid is False
    assert "max_sentences_exceeded" in padded.violations
    assert "unauthorized_extension" in padded.violations


def test_economia_estrita_rejeita_pergunta_nova_ausente_da_fala_autoral() -> None:
    context = _context(
        canonical_line="Poxa... você me salvou.",
        max_sentences=2,
        strict_response_economy=True,
        max_extra_words=10,
    )

    result = evaluate_deterministic_response(
        "Poxa... você me salvou. O que achou do meu biquíni?",
        context,
    )

    assert result.valid is False
    assert "new_conversational_hook" in result.violations


def test_reticencias_internas_nao_criam_frase_extra() -> None:
    context = _context(
        canonical_line="Ainda bem que encontrei você... ir de carro assim é muito melhor, rsrsrs.",
        max_sentences=2,
        strict_response_economy=True,
        max_extra_words=10,
    )

    result = evaluate_deterministic_response(
        "Vou para a do centro, Janio. Ainda bem que encontrei você... ir de carro assim é muito melhor, rsrsrs.",
        context,
    )

    assert result.valid is True
    assert result.violations == ()


def test_fala_livre_nao_e_limitada_por_referencia_audivel_inexistente() -> None:
    context = _context(
        canonical_line=(
            "[PENSAMENTO]\nAgora vou descobrir se ele quer continuar.\n[/PENSAMENTO]"
        ),
        dramatic_direction="Agradecer e mostrar outra tatuagem de forma provocante.",
        strict_response_economy=True,
        max_extra_words=10,
        max_sentences=2,
        free_speech=True,
        authored_thought="Agora vou descobrir se ele quer continuar.",
    )

    result = evaluate_deterministic_response(
        "[PENSAMENTO]\nAgora vou descobrir se ele quer continuar.\n[/PENSAMENTO]\n\n"
        "Obrigada por parar, Janio... olha só essa outra tatuagem aqui perto da minha virilha.",
        context,
    )

    assert result.valid is True
    assert result.violations == ()


def test_transicao_autoral_e_obrigatoria_antes_da_fala() -> None:
    transition = "[ALGUNS MINUTOS DEPOIS — DENTRO DO CARRO.]"
    context = _context(
        canonical_line=f"{transition}\n\nTá sabendo que eu terminei?",
        authored_transition=transition,
        exact_speech="Tá sabendo que eu terminei?",
        strict_response_economy=True,
        max_extra_words=10,
    )

    valid = evaluate_deterministic_response(
        f"{transition}\n\nTá sabendo que eu terminei?",
        context,
    )
    missing = evaluate_deterministic_response(
        "Tá sabendo que eu terminei?",
        context,
    )
    duplicated = evaluate_deterministic_response(
        f"{transition}\n{transition}\n\nTá sabendo que eu terminei?",
        context,
    )

    assert valid.valid is True
    assert missing.violations == ("authored_transition_invalid",)
    assert "authored_transition_invalid" in duplicated.violations


def test_pensamento_inventado_e_rejeitado_quando_beat_nao_o_declara() -> None:
    result = evaluate_deterministic_response(
        "[PENSAMENTO]\nJá estou imaginando o que faremos.\n[/PENSAMENTO]\n\nOi, Doni.",
        _context(authored_thought=""),
    )

    assert result.valid is False
    assert result.violations == ("unexpected_thought",)


def test_ponte_rejeita_deja_vu_literal_do_beat_consumido() -> None:
    context = _context(
        forbidden_literal_texts=(
            "Humm... gostei do jeito dele.",
            "Oi, Nilo... gostei de ver você aqui, meu lindo.",
        )
    )

    repeated = evaluate_deterministic_response(
        "[PENSAMENTO]\nHumm... gostei do jeito dele.\n[/PENSAMENTO]\n\n"
        "Eu me chamo Camilly.",
        context,
    )
    new_reaction = evaluate_deterministic_response("Eu me chamo Camilly.", context)

    assert repeated.valid is False
    assert repeated.violations == (
        "unexpected_thought",
        "forbidden_literal_text_repeated",
    )
    assert new_reaction.valid is True


def test_ponte_rejeita_pergunta_que_criaria_pendencia() -> None:
    context = _context(forbid_new_questions=True, max_questions=0)

    with_question = evaluate_deterministic_response(
        "Gostei do que você disse. O que você faria comigo?",
        context,
    )
    closed_reaction = evaluate_deterministic_response(
        "Gostei do que você disse e quero guardar essa expectativa.",
        context,
    )

    assert with_question.valid is False
    assert with_question.violations == ("bridge_question_created",)
    assert closed_reaction.valid is True


def test_avaliacao_semantica_usa_candidata_explicita_da_tentativa_atual() -> None:
    first = "Gostei. Você não fica só no carinho, né?"
    second = "Gostei do que você contou e senti um arrepio só de imaginar."
    context = _context(forbid_new_questions=True, max_questions=0)

    evaluate_deterministic_response(first, context)
    semantic = parse_semantic_evaluation(
        '{"valid": true, "violations": []}',
        candidate=second,
        context=context,
    )
    current = merge_evaluations(
        evaluate_deterministic_response(second, context), semantic
    )

    assert current.valid is True
    assert current.violations == ()


def test_contexto_separa_fatos_desconhecidos_e_assuntos() -> None:
    rendered = render_beat_context(_context())

    assert "FATOS CONFIRMADOS" in rendered
    assert "Mary está no caixa com compras" in rendered
    assert "FATOS DESCONHECIDOS" in rendered
    assert "o lugar exato onde o usuário deve esperar" in rendered
    assert "ASSUNTOS PERMITIDOS" in rendered
    assert "não podem ser concretizados" in rendered


def test_prompt_semantico_declara_papel_consultivo() -> None:
    prompt = build_semantic_evaluation_prompt(_context())

    assert "avaliador editorial consultivo" in prompt
    assert "sem assumir autoridade para bloquear" in prompt
    assert "compare cada afirmação concreta" in prompt
    assert "metáfora, flerte, humor, duplo sentido" in prompt
    assert "invented_unconfirmed_detail é informativa" in prompt
    assert "Limites de frases e perguntas são orientação de estilo" in prompt
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


def test_merge_mantem_deterministico_soberano() -> None:
    deterministic = evaluate_deterministic_response("Tudo bem. Você pode me confirmar?", _context())
    semantic = parse_semantic_evaluation(
        '{"valid": false, "violations": ["treated_postpone_as_refusal"]}'
    )

    merged = merge_evaluations(deterministic, semantic)

    assert merged.valid is True
    assert merged.violations == ()


def test_merge_nao_esconde_violacao_deterministica() -> None:
    deterministic = ResponseEvaluation(False, ("technical_marker_exposed",))
    semantic = ResponseEvaluation(True, ())

    merged = merge_evaluations(deterministic, semantic)

    assert merged.valid is False
    assert merged.violations == ("technical_marker_exposed",)


def test_rejeicao_semantica_subjetiva_nao_dispara_regeneracao() -> None:
    deterministic = ResponseEvaluation(True, ())
    semantic = ResponseEvaluation(False, ("failed_required_outcome",))

    merged = merge_evaluations(deterministic, semantic)

    assert merged.valid is True
    assert merged.violations == ()


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
