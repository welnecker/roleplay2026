from __future__ import annotations

import pytest

from services.spreadsheet_story_compiler import (
    SpreadsheetStoryError,
    compile_spreadsheet_story,
)


def _base() -> dict:
    return {
        "package_id": "roleplay2026.teste",
        "script_version": "0.0.1",
        "character": {"name": "Mary", "age": 25},
        "blocks": [],
    }


def _row(line_id: str, order: int, instruction: str) -> dict:
    return {
        "package_id": "roleplay2026.teste",
        "script_version": "1.0.0",
        "line_id": line_id,
        "order": order,
        "instruction": instruction,
        "status": "active",
    }


def test_pensamento_e_fala_sao_compilados_na_mesma_resposta() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena", 10, "[CENA supermercado] Estou fazendo compras."),
            _row("supermercado_001", 20, "[BEAT] Eu esbarro no usuário e me desculpo."),
            _row(
                "supermercado_001_pensamento",
                30,
                "[PENSAMENTO] Merda... espero não ter machucado ele.",
            ),
            _row(
                "supermercado_001_fala",
                40,
                "[FALA EXATA] Eita, caralho... desculpa!",
            ),
            _row("fim", 50, "[FIM story_complete] Encerrar a história."),
        ],
        script_version="1.0.0",
    )

    beat = document["blocks"][0]["beats"][0]
    assert beat["beat_id"] == "supermercado_001"
    assert beat["canonical_line"] == (
        "[PENSAMENTO]\n"
        "Merda... espero não ter machucado ele.\n"
        "[/PENSAMENTO]\n\n"
        "Eita, caralho... desculpa!"
    )
    assert beat["next_beat_id"] == "fim"
    assert document["script_version"] == "1.0.0"


def test_transicao_entra_na_mesma_entrega_do_beat_seguinte() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena", 10, "[CENA supermercado] Estou fazendo compras."),
            _row("primeiro", 20, "[BEAT] Eu encerro o primeiro encontro."),
            _row("fala_primeiro", 30, "[FALA] Vou continuar minhas compras."),
            _row(
                "transicao",
                40,
                "[TRANSIÇÃO] MINUTOS DEPOIS — SUPERMERCADO, FILA DO CAIXA",
            ),
            _row("segundo", 50, "[BEAT] Eu reconheço o usuário na fila."),
            _row("pensamento_segundo", 60, "[PENSAMENTO] Olha ele de novo..."),
            _row("fala_segundo", 70, "[FALA] Você de novo?"),
            _row("fim", 80, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )

    beat = document["blocks"][0]["beats"][1]
    assert beat["canonical_line"].startswith(
        "[MINUTOS DEPOIS — SUPERMERCADO, FILA DO CAIXA]\n\n"
    )
    assert "[PENSAMENTO]\nOlha ele de novo...\n[/PENSAMENTO]" in beat["canonical_line"]
    assert beat["canonical_line"].endswith("Você de novo?")


def test_beat_em_terceira_pessoa_e_rejeitado() -> None:
    with pytest.raises(SpreadsheetStoryError, match="primeira pessoa"):
        compile_spreadsheet_story(
            _base(),
            [
                _row("cena", 10, "[CENA supermercado] Estou fazendo compras."),
                _row(
                    "supermercado_001",
                    20,
                    "[BEAT] Mary esbarra no usuário e se desculpa.",
                ),
                _row("fala", 30, "[FALA] Desculpa!"),
                _row("fim", 40, "[FIM story_complete] Encerrar."),
            ],
            script_version="1.0.0",
        )


def test_ponte_e_orientacao_do_mesmo_beat() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena", 10, "[CENA supermercado] Estou fazendo compras."),
            _row("beat", 20, "[BEAT] Eu verifico se ele está bem."),
            _row("fala", 30, "[FALA] Você está bem?"),
            _row(
                "ponte",
                40,
                "[PONTE] Eu reajo sem antecipar o próximo assunto.",
            ),
            _row("fim", 50, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )

    beat = document["blocks"][0]["beats"][0]
    assert beat["dramatic_direction"] == (
        "PONTE: Eu reajo sem antecipar o próximo assunto."
    )
    assert beat["allowed_transitions"]["dismissive"] == "beat"


def test_cena_vazia_e_ignorada_antes_do_primeiro_beat() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena_vazia", 10, "[CENA preparacao] Estou me preparando."),
            _row("cena_real", 20, "[CENA supermercado] Estou fazendo compras."),
            _row("primeiro", 30, "[BEAT] Eu esbarro no usuário."),
            _row("fala", 40, "[FALA] Desculpa!"),
            _row("fim", 50, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )

    assert document["blocks"][0]["block_id"] == "supermercado"
    assert document["blocks"][0]["entry_beat_id"] == "primeiro"
