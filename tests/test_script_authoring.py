from __future__ import annotations

import pytest

from services.script_authoring import (
    ScriptAuthoringError,
    compile_draft_rows,
    package_id_from_title,
    rows_to_tsv,
)


def _draft() -> str:
    return """
[CENA primeiro_encontro] Eu encontro o usuário.

[BEAT] Eu inicio a conversa.

[PENSAMENTO] Quero descobrir como ele reage.

[FALA EXATA] Oi, {{nome}}... que bom ter você aqui.

[PONTE] Eu respondo sem antecipar o próximo beat.

[PÁTIO FINAL despedida] Eu começo a encerrar a história.

[BEAT] Eu aviso que preciso sair.

[FALA EXATA] Preciso ir, {{nome}}.

[BEAT] Eu faço minha última despedida.

[FALA EXATA] Tchau.

[FIM story_complete] Encerrar a história.
""".strip()


def test_package_id_e_gerado_a_partir_do_titulo() -> None:
    assert package_id_from_title("Encontro com Camilly") == (
        "roleplay2026.encontro_com_camilly"
    )


def test_editor_gera_colunas_ids_e_ordens_da_aba_roteiros() -> None:
    rows = compile_draft_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="1.0.0",
        initial_block_id="primeiro_encontro",
    )

    assert rows[0] == {
        "package_id": "roleplay2026.camilly",
        "script_version": "1.0.0",
        "line_id": "primeiro_encontro_cena",
        "order": 10,
        "instruction": "[CENA primeiro_encontro] Eu encontro o usuário.",
        "status": "active",
        "updated_at": "",
    }
    assert rows[1]["line_id"] == "primeiro_encontro_001"
    assert rows[2]["line_id"] == "primeiro_encontro_001_pensamento"
    assert rows[3]["line_id"] == "primeiro_encontro_001_fala"
    assert rows[-1]["line_id"] == "despedida_fim"
    assert [row["order"] for row in rows] == list(range(10, 120, 10))


def test_tsv_tem_cabecalho_oficial_e_preserva_placeholder() -> None:
    rows = compile_draft_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="1.0.0",
        initial_block_id="primeiro_encontro",
    )

    rendered = rows_to_tsv(rows)

    assert rendered.startswith(
        "package_id\tscript_version\tline_id\torder\tinstruction\tstatus\tupdated_at"
    )
    assert "{{nome}}" in rendered


def test_fala_sem_beat_e_bloqueada() -> None:
    with pytest.raises(ScriptAuthoringError, match=r"precisa de \[BEAT\]"):
        compile_draft_rows(
            "[CENA teste] Eu inicio.\n\n[FALA] Oi.\n\n[FIM fim] Encerrar.",
            package_id="roleplay2026.teste",
            script_version="1.0.0",
            initial_block_id="teste",
        )


def test_patio_final_exige_dois_beats() -> None:
    with pytest.raises(ScriptAuthoringError, match="pelo menos dois"):
        compile_draft_rows(
            """
[CENA teste] Eu inicio.
[BEAT] Eu converso.
[FALA] Oi.
[PÁTIO FINAL fim] Eu começo a encerrar.
[BEAT] Eu me despeço.
[FALA] Tchau.
[FIM fim] Encerrar.
""".strip(),
            package_id="roleplay2026.teste",
            script_version="1.0.0",
            initial_block_id="teste",
        )


def test_fim_precisa_ser_ultima_instrucao() -> None:
    with pytest.raises(ScriptAuthoringError, match="última instrução"):
        compile_draft_rows(
            """
[CENA teste] Eu inicio.
[BEAT] Eu converso.
[FALA] Oi.
[FIM fim] Encerrar.
[BEAT] Eu continuo.
""".strip(),
            package_id="roleplay2026.teste",
            script_version="1.0.0",
            initial_block_id="teste",
        )
