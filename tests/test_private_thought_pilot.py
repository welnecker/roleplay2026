from __future__ import annotations

from services.private_thought_pilot import (
    PRIVATE_THOUGHT_VERSION,
    apply_private_thought_overrides,
    sanitize_private_thought_response,
)


def test_publicacao_separa_cena_domestica_da_primeira_mensagem() -> None:
    document = {
        "script_version": "old",
        "blocks": [
            {
                "beats": [
                    {
                        "beat_id": "retorno_casa_003",
                        "type": "dialogue",
                        "canonical_line": "Preciso despistar e mandar um oi...",
                    },
                    {
                        "beat_id": "mensagens_iniciais_001",
                        "type": "dialogue",
                        "canonical_line": "Você tá sozinho agora?",
                    },
                ]
            }
        ],
    }

    result = apply_private_thought_overrides(document)
    home_beat, first_message = result["blocks"][0]["beats"]

    assert result["script_version"] == PRIVATE_THOUGHT_VERSION
    assert home_beat["type"] == "thought"
    assert "não prolongar" in home_beat["dramatic_direction"].casefold()
    assert first_message["canonical_line"] == "Você tá sozinho agora?"
    assert "primeira mensagem" in first_message["dramatic_direction"].casefold()
    assert first_message["max_sentences"] == 1


def test_vazamento_de_janio_para_fala_audivel_usa_fallback() -> None:
    fallback = (
        "[PENSAMENTO]\nPreciso mandar mensagem ao Janio.\n[/PENSAMENTO]\n\n"
        "Tá gelada sim, amor."
    )
    response = (
        "[PENSAMENTO]\nPreciso mandar mensagem ao Janio.\n[/PENSAMENTO]\n\n"
        "Tá gelada sim, amor. Nossa, Janio... que homem."
    )

    assert sanitize_private_thought_response(response, fallback) == fallback


def test_resposta_com_um_pensamento_e_fala_segura_e_normalizada() -> None:
    fallback = (
        "[PENSAMENTO]\nPreciso mandar mensagem ao Janio.\n[/PENSAMENTO]\n\n"
        "Tá gelada sim, amor."
    )
    response = (
        "[PENSAMENTO]\nPreciso achar um momento para falar com Janio.\n[/PENSAMENTO]\n\n"
        "Tá trincando, amor. Já levo uma para você."
    )

    assert sanitize_private_thought_response(response, fallback) == response


def test_pensamento_no_meio_e_movido_para_o_inicio() -> None:
    fallback = (
        "[PENSAMENTO]\nPreciso mandar mensagem ao Janio.\n[/PENSAMENTO]\n\n"
        "Tá gelada sim, amor."
    )
    response = (
        "Está trincando, do jeito que você gosta.\n\n"
        "[PENSAMENTO]\n"
        "O Alfredo nem imagina, mas preciso mandar mensagem ao Janio.\n"
        "[/PENSAMENTO]\n\n"
        "Vou guardar as coisas e já levo para você."
    )

    normalized = sanitize_private_thought_response(response, fallback)

    assert normalized.startswith("[PENSAMENTO]")
    assert normalized.index("[/PENSAMENTO]") < normalized.index("Está trincando")
    assert "Está trincando, do jeito que você gosta." in normalized
    assert "Vou guardar as coisas e já levo para você." in normalized


def test_handoff_rejeita_residuo_da_conversa_com_alfredo() -> None:
    fallback = (
        "[PENSAMENTO]\n"
        "Dei a cerveja... ele está satisfeito. Agora que estou sozinha, vou mandar uma mensagem para o Janio.\n"
        "[/PENSAMENTO]\n\n"
        "Você tá sozinho agora?"
    )
    response = (
        "[PENSAMENTO]\nAgora posso falar com Janio.\n[/PENSAMENTO]\n\n"
        "Prontinho, amor. Aproveita a cerveja.\n\n"
        "Você tá sozinho agora?"
    )

    assert sanitize_private_thought_response(response, fallback) == fallback


def test_handoff_limpo_preserva_apenas_a_primeira_mensagem() -> None:
    fallback = (
        "[PENSAMENTO]\n"
        "Dei a cerveja... ele está satisfeito. Agora que estou sozinha, vou mandar uma mensagem para o Janio.\n"
        "[/PENSAMENTO]\n\n"
        "Você tá sozinho agora?"
    )
    response = (
        "[PENSAMENTO]\nEle está satisfeito. Agora posso mandar mensagem ao Janio.\n[/PENSAMENTO]\n\n"
        "Você tá sozinho agora?"
    )

    assert sanitize_private_thought_response(response, fallback) == response


def test_mais_de_um_bloco_de_pensamento_e_rejeitado() -> None:
    fallback = "[PENSAMENTO]\nSeguro.\n[/PENSAMENTO]\n\nTudo certo, amor."
    response = (
        "[PENSAMENTO]\nUm.\n[/PENSAMENTO]\n\n"
        "Tudo certo.\n\n[PENSAMENTO]\nDois.\n[/PENSAMENTO]"
    )

    assert sanitize_private_thought_response(response, fallback) == fallback
