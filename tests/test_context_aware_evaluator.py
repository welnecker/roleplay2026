from services.editorial_beat_context import BeatContext
from services.editorial_response_evaluator import (
    build_semantic_evaluation_prompt,
    evaluate_deterministic_response,
    parse_semantic_evaluation,
)


def _context(*, user_intent: str = "accept") -> BeatContext:
    return BeatContext(
        source_beat_id="reencontro_fila_007",
        target_beat_id="reencontro_fila_008",
        objective="Mary confirma o deslocamento com o carrinho.",
        canonical_line=(
            "Prontinho. Olha o tamanho desse carrinho perto do seu! "
            "Você dá conta de empurrar?"
        ),
        dramatic_direction="Não presumir outras ações além do aceite já confirmado.",
        user_intent=user_intent,
        transition_status="decision_confirmed",
        required_outcomes=("reconhecer o aceite", "iniciar somente o movimento do beat alvo"),
        forbidden_outcomes=("repetir o pedido de ajuda", "antecipar a chegada ao carro"),
        allowed_topics=("Mary confirma o deslocamento com o carrinho.",),
        confirmed_facts=("help_to_car: accepted", "local da cena: estacionamento_caminho"),
        unknown_facts=(
            "localização exata, distância ou deslocamento que não tenham sido declarados",
            "quantidade, medida, peso, conteúdo ou composição que não tenham sido declarados",
        ),
        max_sentences=3,
        max_questions=1,
        response_boundary="",
    )


def _prepare(candidate: str, context: BeatContext) -> None:
    build_semantic_evaluation_prompt(context)
    evaluate_deterministic_response(candidate, context)


def test_nao_inventa_pergunta_quando_intencao_e_aceite() -> None:
    context = _context(user_intent="accept")
    candidate = "Prontinho! Você dá conta de empurrar?"
    _prepare(candidate, context)

    result = parse_semantic_evaluation(
        '{"valid": false, "violations": '
        '[{"code": "failed_to_answer_user_question", "evidence": "Prontinho"}]}'
    )

    assert result.valid is True
    assert result.violations == ()


def test_referencia_semantica_tem_precedencia_sobre_proibicao_generica() -> None:
    context = _context()
    candidate = "Olha o tamanho desse carrinho perto do seu! Você dá conta de empurrar?"
    _prepare(candidate, context)

    result = parse_semantic_evaluation(
        '{"valid": false, "violations": '
        '[{"code": "invented_unconfirmed_detail", '
        '"evidence": "tamanho desse carrinho perto do seu"}]}'
    )

    assert result.valid is True
    assert result.violations == ()


def test_detalhe_realmente_nao_autorizado_continua_rejeitado() -> None:
    context = _context()
    candidate = "Me encontra na saída principal em cinco minutos."
    _prepare(candidate, context)

    result = parse_semantic_evaluation(
        '{"valid": false, "violations": '
        '[{"code": "invented_unconfirmed_detail", '
        '"evidence": "saída principal em cinco minutos"}]}'
    )

    assert result.valid is False
    assert result.violations == ("invented_unconfirmed_detail",)


def test_acusacao_precisa_apontar_trecho_da_candidata() -> None:
    context = _context()
    candidate = "Prontinho! Você dá conta de empurrar?"
    _prepare(candidate, context)

    result = parse_semantic_evaluation(
        '{"valid": false, "violations": '
        '[{"code": "invented_unconfirmed_detail", "evidence": "salto alto"}]}'
    )

    assert result.valid is False
    assert result.violations == ("semantic_evaluator_invalid_violations",)
