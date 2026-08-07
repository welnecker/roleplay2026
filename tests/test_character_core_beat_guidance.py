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
    assert "orientação para o beat atual" in context


def test_ponte_usa_regra_do_mesmo_macrobloco() -> None:
    document = load_source_document()

    context = render_character_core_path(
        document,
        beat_id="video_025",
        runtime_phase="bridge",
    )

    assert "macrobloco ativo: ligacao" in context
    assert "regra da ponte" in context
    assert "não usa a conversa para fabricar consentimento" in context
    assert "nunca salto de intimidade" not in context


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
    assert "O beat decide o acontecimento" in context
