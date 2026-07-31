from __future__ import annotations

from services.private_thought_pilot import (
    PRIVATE_THOUGHT_VERSION,
    apply_private_thought_overrides,
    sanitize_private_thought_response,
)


def test_publicacao_transforma_beat_em_pensamento() -> None:
    document = {
        "script_version": "old",
        "blocks": [
            {
                "beats": [
                    {
                        "beat_id": "retorno_casa_003",
                        "type": "dialogue",
                        "canonical_line": "Preciso despistar e mandar um oi...",
                    }
                ]
            }
        ],
    }

    result = apply_private_thought_overrides(document)
    beat = result["blocks"][0]["beats"][0]

    assert result["script_version"] == PRIVATE_THOUGHT_VERSION
    assert beat["type"] == "thought"
    assert "Janio" in beat["canonical_line"]
    assert "fala audível" in beat["dramatic_direction"]


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


def test_mais_de_um_bloco_de_pensamento_e_rejeitado() -> None:
    fallback = "[PENSAMENTO]\nSeguro.\n[/PENSAMENTO]\n\nTudo certo, amor."
    response = (
        "[PENSAMENTO]\nUm.\n[/PENSAMENTO]\n\n"
        "Tudo certo.\n\n[PENSAMENTO]\nDois.\n[/PENSAMENTO]"
    )

    assert sanitize_private_thought_response(response, fallback) == fallback
