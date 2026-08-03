from __future__ import annotations

from services.editorial_diagnostics import finalize_editorial_model_response


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

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == (
        "[PENSAMENTO]\nQuero mais.\n[/PENSAMENTO]\n\n"
        "Ainda não terminei, safado... tenho mais para você.\n\n"
        f"{fallback}"
    )
    assert "antecipar a penetração" not in result.response
    assert result.guard_reason == "motel_canonical_boundary"
    assert result.used_fallback is False


def test_motel_anexa_beat_quando_modelo_responde_mas_o_omite() -> None:
    fallback = "Deixa eu ver se esse garotão subiu de novo..."
    raw = "Você ainda vai descobrir, gostoso... não estou nem perto de terminar."

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == f"{raw}\n\n{fallback}"
    assert result.guard_reason == "motel_canonical_boundary"


def test_despedida_penultima_preserva_pensamento_reacao_e_beat() -> None:
    fallback = "mal posso esperar pra te ver de novo...beijo...tchau..."
    raw = (
        "[PENSAMENTO]\n"
        "Ele não consegue tirar os olhos de mim e eu adoro esse poder que tenho sobre ele.\n"
        "[/PENSAMENTO]\n\n"
        "Safado! Se você continuar olhando assim eu não consigo atravessar aquela porta... rsrsrs.\n\n"
        "Mal posso esperar pra te ver de novo... beijo... tchau..."
    )

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=fallback,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == (
        "[PENSAMENTO]\n"
        "Ele não consegue tirar os olhos de mim e eu adoro esse poder que tenho sobre ele.\n"
        "[/PENSAMENTO]\n\n"
        "Safado! Se você continuar olhando assim eu não consigo atravessar aquela porta... rsrsrs.\n\n"
        f"{fallback}"
    )
    assert result.guard_reason == "integrated_canonical_boundary"
    assert result.used_fallback is False


def test_ultimo_beat_do_reencontro_preserva_resposta_sobre_o_marido() -> None:
    fallback = "Tá bom... então deixa eu ir. Meu telefone já tá vibrando aqui..."
    raw = (
        "[PENSAMENTO]\n"
        "Ele quer saber o tamanho do perigo, mas eu sei manter isso em segredo.\n"
        "[/PENSAMENTO]\n\n"
        "Relaxa, Janio. Ele não vai dar piti porque não vai saber de nada.\n\n"
        "Tá bom... então deixa eu ir. Meu telefone já tá vibrando aqui e eu preciso chegar."
    )

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=fallback,
        fallback=fallback,
        recent_assistant_messages=[],
    )

    assert result.response == (
        "[PENSAMENTO]\n"
        "Ele quer saber o tamanho do perigo, mas eu sei manter isso em segredo.\n"
        "[/PENSAMENTO]\n\n"
        "Relaxa, Janio. Ele não vai dar piti porque não vai saber de nada.\n\n"
        f"{fallback}"
    )
    assert result.guard_reason == "integrated_canonical_boundary"
    assert result.used_fallback is False


def test_fora_do_motel_mantem_resposta_normal() -> None:
    raw = "Chegamos. Vou abrir o porta-malas."

    result = finalize_editorial_model_response(
        raw_response=raw,
        cleaned_response=raw,
        fallback="Fala alternativa.",
        recent_assistant_messages=[],
    )

    assert result.response == raw
    assert result.guard_reason == "model_response_accepted"
