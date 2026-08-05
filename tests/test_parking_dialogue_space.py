from __future__ import annotations

from services.editorial_compiler import compile_editorial_document
from services.editorial_content import load_source_document
from services.editorial_progression import prepare_editorial_script
from services.editorial_runtime_impl import PilotScript


def _script() -> PilotScript:
    document = load_source_document()
    return prepare_editorial_script(PilotScript(compile_editorial_document(document)))


def test_caixa_nao_avanca_diretamente_para_indicacao_do_carro() -> None:
    script = _script()

    assert script.beats["reencontro_fila_008"]["on_user"]["engaged"] == "estacionamento_conversa_001"
    assert script.beats["estacionamento_conversa_001"]["on_user"]["engaged"] == "estacionamento_conversa_002"
    assert script.beats["estacionamento_conversa_002"]["on_user"]["engaged"] == "reencontro_fila_009"


def test_caminho_oferece_dois_turnos_reais_de_conversa() -> None:
    script = _script()
    first = script.beats["estacionamento_conversa_001"]["units"][0]["anchor"].casefold()
    second = script.beats["estacionamento_conversa_002"]["units"][0]["anchor"].casefold()

    assert "o que queria conversar" in first
    assert "estou te ouvindo" in second
    assert "meu carro é aquele" not in first
    assert "meu carro é aquele" not in second


def test_indicacao_do_carro_permanece_depois_da_conversa() -> None:
    script = _script()
    anchor = script.beats["reencontro_fila_009"]["units"][0]["anchor"].casefold()

    assert "meu carro é aquele" in anchor


def test_porta_malas_nao_muda_diretamente_para_pedido_de_nome() -> None:
    script = _script()

    assert script.beats["reencontro_fila_010"]["on_user"]["engaged"] == "porta_malas_conversa_001"
    assert script.beats["porta_malas_conversa_001"]["on_user"]["engaged"] == "porta_malas_conversa_002"
    assert script.beats["porta_malas_conversa_002"]["on_user"]["engaged"] == "reencontro_fila_011"


def test_porta_malas_oferece_dois_turnos_antes_do_nome() -> None:
    script = _script()
    first = script.beats["porta_malas_conversa_001"]["units"][0]["anchor"].casefold()
    second = script.beats["porta_malas_conversa_002"]["units"][0]["anchor"].casefold()

    assert "entendi muito bem" in first
    assert "não vou fingir" in second
    assert "seu nome" not in first
    assert "seu nome" not in second


def test_pedido_de_nome_permanece_depois_da_conversa_no_porta_malas() -> None:
    script = _script()
    anchor = script.beats["reencontro_fila_011"]["units"][0]["anchor"].casefold()

    assert "seu nome" in anchor
