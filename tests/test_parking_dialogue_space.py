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


def test_nome_pendente_nao_repete_o_mecanismo_da_conversa() -> None:
    script = _script()
    beat = script.beats["nome_assunto_pendente_001"]
    anchor = beat["units"][0]["anchor"].casefold()
    instruction = beat["units"][0]["instruction"].casefold()

    assert "condicionou seu nome" not in anchor
    assert "eu não me assusto com ousadia" in anchor
    assert "mecânica da conversa" in instruction
    assert "condicionou uma resposta" in instruction


def test_nome_ja_conhecido_pula_o_pedido_redundante() -> None:
    script = _script()
    beat = script.beats["reencontro_fila_011"]

    assert beat["skip_when_facts"]["user_name"] == "reencontro_fila_012"
    assert beat["skip_when_facts"]["mutual_introduction_completed"] == "reencontro_fila_012"


def test_condicao_do_nome_recebe_uma_resposta_e_o_fluxo_avanca() -> None:
    script = _script()

    assert script.beats["reencontro_fila_011"]["on_user"]["engaged"] == "nome_assunto_pendente_001"
    assert script.beats["nome_assunto_pendente_001"]["on_user"]["engaged"] == "reencontro_fila_012"
    assert "nome_assunto_pendente_002" not in script.beats


def test_folga_do_nome_exige_resposta_efetiva() -> None:
    script = _script()
    beat = script.beats["nome_assunto_pendente_001"]
    instruction = beat["units"][0]["instruction"].casefold()

    assert "efetivamente responder" in instruction or "responder ao conteúdo real" in instruction
    assert beat["max_questions"] == 0
    assert beat["max_sentences"] == 3


def test_confirmacao_do_horario_avanca_diretamente_para_despedida() -> None:
    script = _script()

    assert script.beats["reencontro_fila_014"]["on_user"]["engaged"] == "reencontro_fila_015"
    assert "antes_despedida_conversa_001" not in script.beats


def test_despedidas_finais_sao_indivisiveis() -> None:
    script = _script()

    assert script.beats["reencontro_fila_015"]["response_boundary"] == "integrated_canonical"
    assert script.beats["reencontro_fila_016"]["response_boundary"] == "integrated_canonical"
