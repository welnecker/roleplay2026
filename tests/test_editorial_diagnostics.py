from __future__ import annotations

from services.editorial_diagnostics import finalize_editorial_model_response


def test_repeticao_recente_forca_fallback() -> None:
    recent = [
        "Prontinho... carrinho cheio e pesado, rsrsrsrs. Obrigada pela ajuda.",
    ]
    raw = (
        "Pode deixar, vou devagar. Prontinho... carrinho cheio e pesado, "
        "rsrsrsrs. Obrigada pela ajuda."
    )

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback="Chegamos. Vou abrir o porta-malas.",
        recent_assistant_messages=recent,
    )

    assert result.response == "Chegamos. Vou abrir o porta-malas."
    assert result.repeated_recent_anchor is True
    assert result.used_fallback is True
    assert result.guard_reason == "repeated_recent_anchor"


def test_resposta_nova_e_preservada() -> None:
    raw = "Chegamos. Vou abrir o porta-malas."

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback="Fala alternativa.",
        recent_assistant_messages=["Obrigada por me ajudar com as compras."],
    )

    assert result.response == raw
    assert result.repeated_recent_anchor is False
    assert result.used_fallback is False
    assert result.guard_reason == "model_response_accepted"


def test_validador_preserva_pensamento_reacao_e_anexa_beat_quando_modelo_o_omite() -> None:
    thought = "[PENSAMENTO]\nIsso mexeu comigo.\n[/PENSAMENTO]"
    raw = (
        f"{thought}\n\n"
        "Acertou em cheio... só de imaginar já fico sem rumo.\n\n"
        "Eu continuaria provocando e abriria outra pergunta fora do beat."
    )
    fallback = (
        "Vou fazer uma loucura também... olha... tô tirando o vestido. "
        "Gostou? Fiquei só de calcinha e sutiã..."
    )

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=fallback,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response.startswith(thought)
    assert "Acertou em cheio" in result.response
    assert result.response.endswith(fallback)
    assert "outra pergunta" not in result.response
    assert result.used_fallback is False
    assert result.guard_reason == "integrated_canonical_boundary"


def test_motel_preserva_pensamento_e_termina_no_beat_canonico() -> None:
    thought = (
        "[PENSAMENTO]\n"
        "Ele acha que eu já estou satisfeita, mas eu ainda quero mais.\n"
        "[/PENSAMENTO]"
    )
    fallback = (
        "Você me salvou, gostoso...hummmf...delícia..."
        "quero te dar mais um presente..."
    )
    raw = (
        f"{thought}\n\n"
        "Ainda não, gostoso... você só me deixou querendo mais.\n\n"
        f"{fallback}\n\n"
        "Agora vou antecipar uma ação que pertence ao próximo beat."
    )

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response.startswith(thought)
    assert "Ainda não, gostoso" in result.response
    assert result.response.endswith(fallback)
    assert "antecipar uma ação" not in result.response
    assert result.guard_reason == "motel_canonical_boundary"


def test_nao_preserva_reacao_com_narracao_proibida() -> None:
    fallback = "Me faz um favorzinho?"
    raw = "*Mary sorri e se aproxima* Eu gostei disso."

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=fallback,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == fallback
    assert result.used_fallback is True
    assert result.guard_reason == "validator_fallback"
