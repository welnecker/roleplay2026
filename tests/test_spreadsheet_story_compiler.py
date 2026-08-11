from __future__ import annotations

import pytest

from services.editorial_compiler import compile_editorial_document
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
    assert beat["authored_thought"] == "Merda... espero não ter machucado ele."
    assert beat["exact_speech"] == "Eita, caralho... desculpa!"


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
    assert beat["allowed_transitions"]["dismissive"] == "__generic_disagreement_warning"
    assert beat["has_authored_bridge"] is True
    assert document["bridge_policy"] == {"mode": "required", "beat_ids": ["beat"]}


def test_falas_e_pensamentos_condicionais_sao_preservados_para_o_runtime() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena", 10, "[CENA quarto] Estou esperando o usuário."),
            _row("beat", 20, "[BEAT] Eu recebo {{nome}} com prazer."),
            _row("pensamento_h", 30, "[PENSAMENTO HOMEM] Que homem gostoso."),
            _row("pensamento_m", 40, "[PENSAMENTO MULHER] Que mulher gostosa."),
            _row("fala_h", 50, "[FALA EXATA HOMEM] Oi, {{nome}}... meu lindo."),
            _row("fala_m", 60, "[FALA EXATA MULHER] Oi, {{nome}}... minha linda."),
            _row("fala_n", 70, "[FALA NEUTRA] Oi, {{nome}}... que prazer."),
            _row("fim", 80, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )

    delivery = document["blocks"][0]["beats"][0]["profile_delivery"]
    assert delivery["thought_variants"]["HOMEM"] == "Que homem gostoso."
    assert delivery["thought_variants"]["MULHER"] == "Que mulher gostosa."
    assert delivery["speech_variants"]["HOMEM"] == "Oi, {{nome}}... meu lindo."
    assert delivery["speech_variants"]["MULHER"] == "Oi, {{nome}}... minha linda."
    assert delivery["speech_variants"]["NEUTRA"] == "Oi, {{nome}}... que prazer."
    assert delivery["speech_exact"] is True


def test_beats_da_planilha_declaram_as_quatro_rupturas_do_patio() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena", 10, "[CENA mercado] Estou fazendo compras."),
            _row("beat", 20, "[BEAT] Eu converso com o usuário."),
            _row("fala", 30, "[FALA] Pode falar comigo."),
            _row("fim", 40, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )

    context = document["blocks"][0]["beats"][0]["interaction_context"]
    assert context["terminal_yard_target"] == "__generic_disagreement_warning"
    assert context["terminal_violations"] == [
        "violence_or_threat_against_character",
        "humiliation_or_public_exposure_of_character",
        "explicit_departure_or_refusal_that_abandons_the_story",
        "attempt_to_impose_undeclared_actions_events_or_locations_as_facts",
    ]
    assert "proposta dirigida à personagem" in context["allowed_interactions"][0]


def test_patio_generico_avisa_e_encerra_com_nome_personalizavel() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("cena", 10, "[CENA quarto] Estou esperando o usuário."),
            _row("beat", 20, "[BEAT] Eu inicio a conversa."),
            _row("fala", 30, "[FALA EXATA] Que bom ter você aqui."),
            _row("fim", 40, "[FIM story_complete] Encerrar."),
        ],
        script_version="1.0.0",
    )

    beat = document["blocks"][0]["beats"][0]
    assert beat["allowed_transitions"]["dismissive"] == "__generic_disagreement_warning"
    yard = next(
        block
        for block in document["blocks"]
        if block["block_id"] == "patio_generico_desacordo"
    )
    warning, closing, ending = yard["beats"]
    assert "{{nome}}" in warning["canonical_line"]
    assert "último aviso" in warning["canonical_line"]
    assert closing["terminal_transition"] == ending["beat_id"]
    assert "nossa interação se encerra aqui" in closing["canonical_line"]
    assert ending["ending"] == {
        "run_status": "terminated",
        "ending_code": "generic_user_disagreement",
    }

    compiled = compile_editorial_document(document)
    compiled_closing = next(
        beat
        for beat in compiled["scene"]["beats"]
        if beat["beat_id"] == closing["beat_id"]
    )
    assert compiled_closing["terminal_transition"] == ending["beat_id"]


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


def test_bloco_com_apenas_fim_nao_se_torna_primeiro_bloco() -> None:
    document = compile_spreadsheet_story(
        _base(),
        [
            _row("fim", 10, "[FIM story_complete] Encerrar."),
            _row("cena", 20, "[CENA supermercado] Estou fazendo compras."),
            _row("primeiro", 30, "[BEAT] Eu esbarro no usuário."),
            _row("fala", 40, "[FALA] Desculpa!"),
        ],
        script_version="1.0.0",
    )

    assert document["blocks"][0]["entry_beat_id"] == "primeiro"
    endings = [
        beat
        for block in document["blocks"]
        for beat in block["beats"]
        if beat["type"] == "ending"
    ]
    assert any(ending["beat_id"] == "fim" for ending in endings)

    compiled = compile_editorial_document(document)
    assert compiled["scene"]["first_beat_id"] == "primeiro"
