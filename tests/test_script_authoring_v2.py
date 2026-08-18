from __future__ import annotations

import pytest

from services.script_authoring import ScriptAuthoringError
from services.script_authoring_v2 import (
    compile_v2_rows,
    parse_v2_draft,
    preview_v2_frames,
)


DRAFT = """[DESCRIÇÃO] Camilly e {{nome}} encontram Renan na praia.

[FALA camilly] Eu cumprimento Renan com surpresa.

[FALA renan] Eu respondo e observo quem está com ela.

[PENSAMENTO usuario] A reação dos dois parece íntima.

[FALA renan] Eu faço uma segunda observação para Camilly.

[DESCRIÇÃO] Os três seguem juntos até o quiosque.

[PENSAMENTO camilly] Preciso entender o que Renan pretende.

[FALA usuario] Eu puxo um assunto novo para aliviar o clima.
"""


def test_compilador_v2_gera_quadros_e_line_ids_por_ator() -> None:
    rows = compile_v2_rows(
        DRAFT,
        package_id="roleplay2026.camilly_renan",
        script_version="200",
        frame_prefix="encontro",
        start_order=10,
        order_step=10,
    )

    assert [row["line_id"] for row in rows] == [
        "encontro_001_descricao",
        "encontro_001_camilly_fala_01",
        "encontro_001_renan_fala_01",
        "encontro_001_usuario_pensamento_01",
        "encontro_001_renan_fala_02",
        "encontro_002_descricao",
        "encontro_002_camilly_pensamento_01",
        "encontro_002_usuario_fala_01",
    ]
    assert [row["order"] for row in rows] == list(range(10, 90, 10))
    assert rows[1]["instruction"].startswith("[FALA camilly]")
    assert rows[3]["instruction"].startswith("[PENSAMENTO usuario]")


def test_v2_preserva_numero_inicial_do_quadro() -> None:
    rows = compile_v2_rows(
        "[DESCRIÇÃO] Continuação.\n\n[FALA renan] Eu continuo a conversa.",
        package_id="roleplay2026.camilly_renan",
        script_version="201",
        frame_prefix="praia",
        start_frame_number=7,
    )

    assert rows[0]["line_id"] == "praia_007_descricao"
    assert rows[1]["line_id"] == "praia_007_renan_fala_01"


def test_v2_aceita_quantidade_arbitraria_de_personagens() -> None:
    items = parse_v2_draft(
        """[DESCRIÇÃO] Todos estão juntos.
[FALA camilly] Eu falo primeiro.
[FALA renan] Eu falo depois.
[FALA usuario] Eu respondo.
[FALA juninho] Eu entro na conversa.
[PENSAMENTO mary] Eu observo todos em silêncio.
"""
    )

    assert [item.actor for item in items if item.actor] == [
        "camilly",
        "renan",
        "usuario",
        "juninho",
        "mary",
    ]


def test_v2_rejeita_entry_antes_da_primeira_descricao() -> None:
    with pytest.raises(ScriptAuthoringError, match="precisa de \[DESCRIÇÃO\] anterior"):
        compile_v2_rows(
            "[FALA camilly] Eu começo falando.\n\n[DESCRIÇÃO] Depois vem a cena.",
            package_id="roleplay2026.teste",
            script_version="200",
            frame_prefix="teste",
        )


def test_preview_v2_agrupa_entries_no_quadro_correto() -> None:
    frames = preview_v2_frames(DRAFT, frame_prefix="encontro")

    assert len(frames) == 2
    assert frames[0].frame_id == "encontro_001"
    assert len(frames[0].entries) == 4
    assert frames[0].entries[0].actor == "camilly"
    assert frames[0].entries[2].kind == "PENSAMENTO"
    assert frames[1].frame_id == "encontro_002"
    assert len(frames[1].entries) == 2


def test_v2_rejeita_tags_legadas_no_modo_novo() -> None:
    with pytest.raises(ScriptAuthoringError, match="Tag não reconhecida no modo V2"):
        parse_v2_draft("[DESCRIÇÃO] Cena.\n\n[BEAT] Eu faço algo.")
