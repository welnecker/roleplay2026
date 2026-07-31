from __future__ import annotations

from services.pilot_diagnostics import finalize_model_response


def test_repeticao_recente_forca_fallback() -> None:
    recent = [
        "Prontinho... carrinho cheio e pesado, rsrsrsrs. Obrigada pela ajuda.",
    ]
    raw = (
        "Pode deixar, vou devagar. Prontinho... carrinho cheio e pesado, "
        "rsrsrsrs. Obrigada pela ajuda."
    )

    result = finalize_model_response(
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

    result = finalize_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback="Fala alternativa.",
        recent_assistant_messages=["Obrigada por me ajudar com as compras."],
    )

    assert result.response == raw
    assert result.repeated_recent_anchor is False
    assert result.used_fallback is False
    assert result.guard_reason == "model_response_accepted"
