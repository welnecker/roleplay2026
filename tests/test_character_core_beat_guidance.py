from __future__ import annotations

from services.editorial_content import load_source_document
from services.narrative_context import build_narrative_context, render_character_core_path


def test_character_path_declara_os_tres_macroblocos() -> None:
    document = load_source_document()
    path = document["character_core_path"]

    blocks = {item["block_id"]: item for item in path["blocks"]}

    assert set(blocks) == {"supermercado", "ligacao", "motel"}
    assert blocks["supermercado"]["beat_prefixes"]
    assert blocks["ligacao"]["beat_prefixes"]
    assert blocks["motel"]["beat_prefixes"]
    assert "mesmo arco" in " ".join(path["continuity"])


def test_contexto_renderiza_somente_o_caminho_do_beat_ativo() -> None:
    document = load_source_document()

    context = build_narrative_context(
        document,
        [],
        {},
        beat_id="mensagens_iniciais_003",
        runtime_phase="canonical",
    )

    assert "CAMINHO VIVO DE INTERPRETAÇÃO" in context
    assert "macrobloco ativo: ligacao" in context
    assert "macrobloco ativo: supermercado" not in context
    assert "macrobloco ativo: motel" not in context
    assert "família do beat: mensagens_iniciais_" in context
    assert "orientação psicológica deste beat" in context


def test_ponte_usa_regra_do_mesmo_macrobloco() -> None:
    document = load_source_document()

    context = render_character_core_path(
        document,
        beat_id="video_025",
        runtime_phase="bridge",
    )

    assert "macrobloco ativo: ligacao" in context
    assert "família do beat: video_" in context
    assert "regra da ponte" in context
    assert "não usa a conversa para fabricar consentimento" in context
    assert "nunca salto de intimidade" not in context


def test_pensamento_exige_desejo_concreto_em_vez_de_frase_generica() -> None:
    document = load_source_document()
    path = document["character_core_path"]
    contract = " ".join(path["thought_contract"])

    assert "concreto, visceral e pessoal" in contract
    assert "nomear o que chamou a atenção de Mary" in contract
    assert "frases genéricas" in contract


def test_caminho_bloqueia_metalinguagem_e_preserva_fatos_resolvidos() -> None:
    document = load_source_document()
    path = document["character_core_path"]
    contract = " ".join(path["conversational_contract"])

    assert "somente ao que o usuário efetivamente disse" in contract
    assert "Nunca fale como se soubesse a próxima fala" in contract
    assert "Nunca descreva a mecânica da conversa" in contract
    assert "informação já foi dada" in contract


def test_caminho_nao_substitui_o_contrato_do_beat() -> None:
    document = load_source_document()

    context = build_narrative_context(
        document,
        [],
        {},
        beat_id="motel_001",
        runtime_phase="canonical",
    )

    assert "NÚCLEO VIVO E AUTORITATIVO DE MARY" in context
    assert "CAMINHO VIVO DE INTERPRETAÇÃO" in context
    assert "família do beat: motel_" in context
    assert "O beat decide o acontecimento" in context
