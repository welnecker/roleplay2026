from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import prepare_editorial_script
from services.editorial_runtime_impl import PilotScript


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_caminho_oferece_uma_resposta_e_avanca_para_o_carro() -> None:
    script = _script()

    assert script.beats["reencontro_fila_008"]["on_user"]["engaged"] == "estacionamento_conversa_001"
    assert script.beats["estacionamento_conversa_001"]["on_user"]["engaged"] == "reencontro_fila_009"
    assert "estacionamento_conversa_002" not in script.beats


def test_resposta_no_caminho_exige_posicao_clara_e_curta() -> None:
    script = _script()
    beat = script.beats["estacionamento_conversa_001"]
    instruction = beat["units"][0]["instruction"].casefold()

    assert beat["max_sentences"] == 2
    assert beat["max_questions"] == 0
    assert "sim, não ou limite claro" in instruction
    assert "não pedir nova explicação" in instruction


def test_porta_malas_responde_uma_vez_antes_do_nome() -> None:
    script = _script()

    assert script.beats["reencontro_fila_010"]["on_user"]["engaged"] == "porta_malas_conversa_001"
    assert script.beats["porta_malas_conversa_001"]["on_user"]["engaged"] == "reencontro_fila_011"
    assert "porta_malas_conversa_002" not in script.beats


def test_porta_malas_nao_fica_apenas_em_confirmacao_generica() -> None:
    script = _script()
    beat = script.beats["porta_malas_conversa_001"]
    anchor = beat["units"][0]["anchor"].casefold()
    instruction = beat["units"][0]["instruction"].casefold()

    assert "proposta bem direta" in anchor
    assert "posição inequívoca" in instruction
    assert beat["max_sentences"] == 2


def test_condicao_do_nome_recebe_uma_resposta_e_o_fluxo_avanca() -> None:
    script = _script()

    assert script.beats["reencontro_fila_011"]["on_user"]["engaged"] == "nome_assunto_pendente_001"
    assert script.beats["nome_assunto_pendente_001"]["on_user"]["engaged"] == "reencontro_fila_012"
    assert "nome_assunto_pendente_002" not in script.beats


def test_folga_do_nome_exige_resposta_efetiva() -> None:
    script = _script()
    beat = script.beats["nome_assunto_pendente_001"]
    instruction = beat["units"][0]["instruction"].casefold()

    assert "efetivamente responder" in instruction
    assert "explicitar o pedido concreto" in instruction
    assert beat["max_questions"] == 0
    assert beat["max_sentences"] == 2


def test_confirmacao_do_horario_tem_uma_resposta_antes_da_despedida() -> None:
    script = _script()

    assert script.beats["reencontro_fila_014"]["on_user"]["engaged"] == "antes_despedida_conversa_001"
    assert script.beats["antes_despedida_conversa_001"]["on_user"]["engaged"] == "reencontro_fila_015"
    assert "antes_despedida_conversa_002" not in script.beats


def test_resposta_final_nao_adia_o_assunto_para_depois() -> None:
    script = _script()
    beat = script.beats["antes_despedida_conversa_001"]
    instruction = beat["units"][0]["instruction"].casefold()

    assert "resposta clara na mesma fala" in instruction
    assert "depois eu digo" in instruction
    assert beat["max_questions"] == 0
    assert beat["max_sentences"] == 2
