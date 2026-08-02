from __future__ import annotations

from services.pilot_diagnostics import finalize_model_response


def test_motel_preserva_reacao_e_corta_tudo_depois_do_beat() -> None:
    fallback = (
        "Você me salvou, gostoso...hummmf...delícia..."
        "quero te dar mais um presente..."
    )
    raw = (
        "[PENSAMENTO]\nQuero mais.\n[/PENSAMENTO]\n\n"
        "Ainda não terminei, safado... tenho mais para você.\n\n"
        "Você me salvou, gostoso... hummmf... delícia... "
        "quero te dar mais um presente...\n\n"
        "Agora eu quero antecipar a penetração e os movimentos seguintes."
    )

    result = finalize_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == (
        "Ainda não terminei, safado... tenho mais para você.\n\n"
        f"{fallback}"
    )
    assert "antecipar a penetração" not in result.response
    assert result.guard_reason == "motel_canonical_boundary"
    assert result.used_fallback is False


def test_motel_anexa_beat_quando_modelo_responde_mas_o_omite() -> None:
    fallback = "Deixa eu ver se esse garotão subiu de novo..."
    raw = "Você ainda vai descobrir, gostoso... não estou nem perto de terminar."

    result = finalize_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == f"{raw}\n\n{fallback}"
    assert result.guard_reason == "motel_canonical_boundary"


def test_fora_do_motel_mantem_resposta_normal() -> None:
    raw = "Chegamos. Vou abrir o porta-malas."

    result = finalize_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback="Fala alternativa.",
        recent_assistant_messages=[],
    )

    assert result.response == raw
    assert result.guard_reason == "model_response_accepted"
