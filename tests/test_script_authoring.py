from __future__ import annotations

import pytest

from services.script_authoring import (
    ScriptAuthoringError,
    clear_authoring_state,
    compile_draft_rows,
    package_id_from_title,
    rows_to_tsv,
    synchronized_package_id,
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


def test_sugestao_de_package_id_acompanha_titulo_sem_apagar_edicao_manual() -> None:
    generated, suggestion = synchronized_package_id("Encontro com Camilly", "", "")
    assert generated == "roleplay2026.encontro_com_camilly"

    updated, new_suggestion = synchronized_package_id(
        "Segunda história", generated, suggestion
    )
    assert updated == "roleplay2026.segunda_historia"

    manual, _ = synchronized_package_id(
        "Terceira história", "roleplay2026.id_autoral", new_suggestion
    )
    assert manual == "roleplay2026.id_autoral"


def test_limpeza_remove_rascunho_e_linhas_sem_afetar_outro_estado() -> None:
    state = {
        "draft": "[BEAT] Eu começo.",
        "rows": [{"line_id": "teste"}],
        "login": "ok",
    }

    clear_authoring_state(state, draft_key="draft", rows_key="rows")

    assert state == {"draft": "", "login": "ok"}


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


def test_editor_aceita_tags_interpretadas() -> None:
    rows = compile_draft_rows(
        """[CENA teste] Eu inicio.\n[BEAT] Eu provoco o usuário.\n[PENSAMENTO INTERPRETADO] Meu desejo está crescendo.\n[FALA INTERPRETADA] Chega mais perto.\n[FIM story_complete] Eu encerro.""",
        package_id="roleplay2026.teste",
        script_version="1",
        initial_block_id="teste",
    )

    assert rows[2]["instruction"] == "[PENSAMENTO INTERPRETADO] Meu desejo está crescendo."
    assert rows[3]["instruction"] == "[FALA INTERPRETADA] Chega mais perto."


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


def test_tags_direcionadas_sao_preservadas_e_recebem_ids_identificaveis() -> None:
    draft = """
[CENA encontro] Eu recebo o usuário.
[BEAT] Eu começo a conversa.
[PENSAMENTO HOMEM] Humm... gostei do jeito dele.
[PENSAMENTO MULHER] Humm... gostei do jeito dela.
[PENSAMENTO NEUTRA] Humm... gostei dessa aproximação.
[PENSAMENTO CORPO_MASCULINO] Eu desejo conhecer esse corpo masculino.
[PENSAMENTO CORPO_FEMININO] Eu desejo conhecer esse corpo feminino.
[PENSAMENTO CORPO_INTERSEXO] Eu desejo conhecer esse corpo intersexo.
[FALA EXATA HOMEM] Oi, {{nome}}... meu lindo.
[FALA EXATA MULHER] Oi, {{nome}}... minha linda.
[FALA EXATA NEUTRA] Oi, {{nome}}... que prazer.
[FIM story_complete] Encerrar a história.
""".strip()

    rows = compile_draft_rows(
        draft,
        package_id="roleplay2026.direcionada",
        script_version="1.0.0",
        initial_block_id="encontro",
    )

    instructions = [str(row["instruction"]) for row in rows]
    line_ids = [str(row["line_id"]) for row in rows]
    assert instructions[2:] == [
        "[PENSAMENTO HOMEM] Humm... gostei do jeito dele.",
        "[PENSAMENTO MULHER] Humm... gostei do jeito dela.",
        "[PENSAMENTO NEUTRA] Humm... gostei dessa aproximação.",
        "[PENSAMENTO CORPO_MASCULINO] Eu desejo conhecer esse corpo masculino.",
        "[PENSAMENTO CORPO_FEMININO] Eu desejo conhecer esse corpo feminino.",
        "[PENSAMENTO CORPO_INTERSEXO] Eu desejo conhecer esse corpo intersexo.",
        "[FALA EXATA HOMEM] Oi, {{nome}}... meu lindo.",
        "[FALA EXATA MULHER] Oi, {{nome}}... minha linda.",
        "[FALA EXATA NEUTRA] Oi, {{nome}}... que prazer.",
        "[FIM story_complete] Encerrar a história.",
    ]
    assert line_ids[2:11] == [
        "encontro_001_pensamento_homem",
        "encontro_001_pensamento_mulher",
        "encontro_001_pensamento_neutra",
        "encontro_001_pensamento_corpo_masculino",
        "encontro_001_pensamento_corpo_feminino",
        "encontro_001_pensamento_corpo_intersexo",
        "encontro_001_fala_homem",
        "encontro_001_fala_mulher",
        "encontro_001_fala_neutra",
    ]
    assert len(line_ids) == len(set(line_ids))
    assert "[FALA EXATA HOMEM] Oi, {{nome}}... meu lindo." in rows_to_tsv(rows)


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


@pytest.mark.parametrize(
    "thought",
    (
        "Humm... tive uma ideia safada agora.",
        "Percebi o jeito dele e decidi provocar.",
        "Fiz uma escolha e vou manter o assunto.",
        "Vi a reação dele e gostei.",
        "Vamos ver se ele cai nessa, rsrsrs.",
        "Tô ficando curiosa com essa aproximação.",
    ),
)
def test_pensamento_aceita_verbos_naturais_com_pronome_oculto(thought: str) -> None:
    draft = f"""
[CENA encontro] Eu encontro o usuário.
[BEAT] Eu começo a conversa.
[PENSAMENTO] {thought}
[FALA] Oi.
[FIM story_complete] Encerrar.
""".strip()

    rows = compile_draft_rows(
        draft,
        package_id="roleplay2026.teste",
        script_version="1.0.0",
        initial_block_id="encontro",
    )

    assert rows[2]["instruction"] == f"[PENSAMENTO] {thought}"


def test_pensamento_aceita_fragmento_interno_sem_pronome_ou_verbo() -> None:
    rows = compile_draft_rows(
        """
[CENA encontro] Eu encontro o usuário.
[BEAT] Eu começo a conversa.
[PENSAMENTO] Que homem gostoso... olha ele de novo.
[FALA] Oi.
[FIM story_complete] Encerrar.
""".strip(),
        package_id="roleplay2026.teste",
        script_version="1.0.0",
        initial_block_id="encontro",
    )

    assert rows[2]["instruction"] == (
        "[PENSAMENTO] Que homem gostoso... olha ele de novo."
    )
