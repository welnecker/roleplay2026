from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "roteiro_editor_desktop" / "core.py"
EDITOR_DIR = MODULE_PATH.parent
if str(EDITOR_DIR) not in sys.path:
    sys.path.insert(0, str(EDITOR_DIR))
spec = importlib.util.spec_from_file_location("roteiro_editor_desktop_core", MODULE_PATH)
assert spec and spec.loader
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def _draft() -> str:
    return """[DESCRIÇÃO] Camilly entra no carro.
[FALA camilly] Oi, {{nome}}.
[PENSAMENTO camilly] Eu observo a reação dele.
[DESCRIÇÃO] Camilly fecha a porta.
[FALA usuario] Tudo bem?
"""


def test_columns_match_current_sheet_contract() -> None:
    assert core.COLUMNS == (
        "package_id",
        "script_version",
        "line_id",
        "order",
        "instruction",
        "status",
        "image_id",
    )


def test_compile_rows_generates_v2_ids_and_orders() -> None:
    rows = core.compile_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
        start_order=10,
        order_step=10,
        start_frame_number=1,
    )
    assert [row["line_id"] for row in rows] == [
        "encontro_001_descricao",
        "encontro_001_camilly_fala_01",
        "encontro_001_camilly_pensamento_01",
        "encontro_002_descricao",
        "encontro_002_usuario_fala_01",
    ]
    assert [row["order"] for row in rows] == [10, 20, 30, 40, 50]
    assert all(tuple(row.keys()) == core.COLUMNS for row in rows)


def test_balloon_actor_suffix_is_preserved_in_export() -> None:
    rows = core.compile_rows(
        "[DESCRIÇÃO] Cena inicial.\n[FALA camilly_balao] Olha pra mim.",
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
    )
    assert rows[1]["instruction"] == "[FALA camilly_balao] Olha pra mim."
    assert rows[1]["line_id"] == "encontro_001_camilly_balao_fala_01"


def test_exact_and_interpreted_speech_tags_are_preserved_in_export() -> None:
    rows = core.compile_rows(
        """[DESCRIÇÃO] Cena inicial.
[FALA EXATA camilly] Oi, {{nome}}.
[FALA INTERPRETADA usuario_balao] Eu reajo com intensidade.
""",
        package_id="roleplay2026.camilly",
        script_version="202",
        frame_prefix="encontro",
    )
    assert rows[1]["instruction"] == "[FALA EXATA camilly] Oi, {{nome}}."
    assert rows[1]["line_id"] == "encontro_001_camilly_fala_01"
    assert rows[2]["instruction"] == "[FALA INTERPRETADA usuario_balao] Eu reajo com intensidade."
    assert rows[2]["line_id"] == "encontro_001_usuario_balao_fala_01"


def test_smack_e_exportado_antes_da_fala_sem_consumir_ator_ou_imagem() -> None:
    rows = core.compile_rows(
        """[DESCRIÇÃO] O professor se aproxima do ombro de Mary.
[FALA professor] Fique tranquila... sou eu.
[ONOMATOPEIA smack x=69 y=48 delay=350]
[FALA mary] Ai!!! Que susto, prof... rsrs
""",
        package_id="roleplay2026.casada_frustrada",
        script_version="204",
        frame_prefix="mascara",
    )

    assert rows[2]["line_id"] == "mascara_001_onomatopeia_01"
    assert rows[2]["instruction"] == (
        "[ONOMATOPEIA smack x=69 y=48 delay=350 duracao=1200 dx=32 dy=-10]"
    )
    assert rows[2]["image_id"] == ""
    assert rows[3]["line_id"] == "mascara_001_mary_fala_01"


def test_smack_precisa_ficar_imediatamente_antes_da_fala_alvo() -> None:
    with pytest.raises(core.EditorError, match="imediatamente antes"):
        core.compile_rows(
            """[DESCRIÇÃO] Cena.
[ONOMATOPEIA smack x=69 y=48]
[DESCRIÇÃO] Outra cena.
[FALA mary] Oi.
""",
            package_id="roleplay2026.casada_frustrada",
            script_version="204",
            frame_prefix="mascara",
        )


def test_gendered_name_placeholders_are_preserved_in_export() -> None:
    rows = core.compile_rows(
        """[DESCRIÇÃO] Camilly observa {{*nome}}.
[PENSAMENTO camilly] Será que {{**nome}} lembra de mim?
[FALA EXATA camilly] Oi, {{nome}}.
""",
        package_id="roleplay2026.camilly",
        script_version="203",
        frame_prefix="encontro",
    )
    assert rows[0]["instruction"] == "[DESCRIÇÃO] Camilly observa {{*nome}}."
    assert "{{**nome}}" in str(rows[1]["instruction"])
    assert rows[2]["instruction"] == "[FALA EXATA camilly] Oi, {{nome}}."


def test_elenco_aceita_quantidade_livre_e_tags_por_personagem() -> None:
    cast = core.normalize_cast_members(
        [
            {
                "actor_id": "Mary",
                "label": "A esposa",
                "default_name": "Mary",
                "gender": "feminine",
            },
            {
                "actor_id": "marido",
                "label": "O marido",
                "default_name": "Doni",
                "gender": "masculine",
            },
            {
                "actor_id": "vizinha",
                "label": "A vizinha",
                "default_name": "Sandra",
                "gender": "feminine",
            },
        ]
    )
    draft = """[DESCRIÇÃO] {{nome:mary}} observa {{nome:vizinha}}.
[FALA mary] Oi, {{nome:vizinha}}.
[PENSAMENTO marido] Conheço {{nome:mary}}.
"""

    assert [item["actor_id"] for item in core.validate_draft_cast(draft, cast)] == [
        "mary",
        "marido",
        "vizinha",
    ]


def test_elenco_recusa_tag_de_personagem_nao_cadastrado() -> None:
    cast = [
        {
            "actor_id": "mary",
            "label": "A esposa",
            "default_name": "Mary",
            "gender": "feminine",
        }
    ]
    try:
        core.validate_draft_cast(
            "[DESCRIÇÃO] Cena.\n[FALA professor] Olá, {{nome:mary}}.",
            cast,
        )
    except core.EditorError as exc:
        assert "professor" in str(exc)
    else:
        raise AssertionError("Ator não cadastrado deveria ser rejeitado")


def test_manifesto_exportado_contem_elenco_e_nomes_iniciais() -> None:
    rendered = core.cast_manifest_yaml(
        [
            {
                "actor_id": "mary",
                "label": "A esposa",
                "default_name": "Mary",
                "gender": "feminine",
            },
            {
                "actor_id": "usuario",
                "label": "O marido",
                "default_name": "Doni",
                "gender": "masculine",
            },
        ]
    )

    assert "cast_customization:" in rendered
    assert "actor_id: mary" in rendered
    assert 'default_name: "Doni"' in rendered
    assert "gender: masculine" in rendered


def test_projeto_antigo_e_convertido_para_elenco_editavel() -> None:
    cast = core.cast_members_from_legacy_actors("Mary, Doni, mary")

    assert cast == [
        {
            "actor_id": "mary",
            "label": "A personagem",
            "default_name": "Mary",
            "gender": "neutral",
        },
        {
            "actor_id": "doni",
            "label": "A personagem",
            "default_name": "Doni",
            "gender": "neutral",
        },
    ]


def test_exportacao_inclui_arquivos_de_elenco(tmp_path: Path) -> None:
    cast = [
        {
            "actor_id": "mary",
            "label": "A esposa",
            "default_name": "Mary",
            "gender": "feminine",
        }
    ]
    rows = core.compile_rows(
        "[DESCRIÇÃO] {{nome:mary}} chega.",
        package_id="roleplay2026.casada_frustrada",
        script_version="200",
        frame_prefix="encontro",
    )

    core.export_package(
        tmp_path,
        rows=rows,
        image_sources={},
        project_payload={"cast_members": cast},
    )

    manifest = (tmp_path / "elenco_manifest.yaml").read_text(encoding="utf-8")
    guide = (tmp_path / "ELENCO-E-TAGS.txt").read_text(encoding="utf-8")
    assert "actor_id: mary" in manifest
    assert "{{nome:mary}}" in guide


def test_fim_historia_sem_texto_encerra_o_ultimo_quadro() -> None:
    rows = core.compile_rows(
        "[DESCRIÇÃO] Último encontro.\n[FALA mary] Até logo.\n[FIM_HISTORIA]",
        package_id="roleplay2026.casada_frustrada",
        script_version="200",
        frame_prefix="encontro",
    )

    assert rows[-1]["line_id"] == "encontro_001_fim_historia"
    assert rows[-1]["instruction"] == "[FIM_HISTORIA]"
    assert rows[-1]["image_id"] == ""


def test_fim_historia_com_texto_aceita_nome_e_imagem_propria() -> None:
    draft = (
        "[DESCRIÇÃO] Último encontro.\n"
        "[FALA mary] Até logo.\n"
        "[FIM_HISTORIA] Gostou da aventura de {{nome:mary}}?"
    )
    rows = core.compile_rows(
        draft,
        package_id="roleplay2026.casada_frustrada",
        script_version="200",
        frame_prefix="encontro",
        image_map={"encontro_001_fim_historia": "mary99.webp"},
    )

    assert rows[-1]["instruction"] == (
        "[FIM_HISTORIA] Gostou da aventura de {{nome:mary}}?"
    )
    assert rows[-1]["image_id"] == "mary99.webp"
    core.validate_draft_cast(
        draft,
        [
            {
                "actor_id": "mary",
                "label": "A esposa",
                "default_name": "Mary",
                "gender": "feminine",
            }
        ],
    )


def test_fim_historia_deve_ser_unico_e_ultima_linha() -> None:
    invalid_drafts = (
        "[DESCRIÇÃO] Cena.\n[FIM_HISTORIA]\n[FALA mary] Depois.",
        "[DESCRIÇÃO] Cena.\n[FIM_HISTORIA]\n[FIM_HISTORIA]",
    )

    for draft in invalid_drafts:
        try:
            core.parse_draft(draft)
        except core.EditorError as exc:
            assert "[FIM_HISTORIA]" in str(exc)
        else:
            raise AssertionError("Encerramento inválido deveria ser rejeitado")


def test_fim_historia_exige_quadro_anterior() -> None:
    try:
        core.parse_draft("[FIM_HISTORIA]")
    except core.EditorError as exc:
        assert "[DESCRIÇÃO]" in str(exc)
    else:
        raise AssertionError("Encerramento sem quadro deveria ser rejeitado")


def test_timeline_edita_fim_historia_com_texto_opcional() -> None:
    from app_image_first_timeline import ScriptEditor as TimelineEditor

    assert TimelineEditor._parse_instruction(  # type: ignore[arg-type]
        None,
        "[FIM_HISTORIA] Até a próxima!",
    ) == ("FIM_HISTORIA", "", "Até a próxima!")
    assert TimelineEditor._instruction_from_editor(  # type: ignore[arg-type]
        None,
        "FIM_HISTORIA",
        "",
        "",
    ) == "[FIM_HISTORIA]"


def test_speech_delivery_requires_actor() -> None:
    try:
        core.parse_draft("[DESCRIÇÃO] Cena.\n[FALA EXATA] Oi.")
    except core.EditorError as exc:
        assert "exige um ator" in str(exc)
    else:
        raise AssertionError("[FALA EXATA] sem ator deveria ser rejeitada")


def test_recompiled_edit_can_change_dialogue_kind_and_keep_position() -> None:
    original = core.compile_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
        start_order=10,
        order_step=10,
    )
    instructions = [str(row["instruction"]) for row in original]
    instructions[1] = "[PENSAMENTO camilly] Agora eu observo em silêncio."
    edited = core.compile_rows(
        "\n\n".join(instructions),
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
        start_order=10,
        order_step=10,
    )
    assert edited[1]["order"] == 20
    assert edited[1]["line_id"] == "encontro_001_camilly_pensamento_01"
    assert edited[1]["instruction"] == "[PENSAMENTO camilly] Agora eu observo em silêncio."


def test_image_map_is_applied_only_to_exact_line() -> None:
    rows = core.compile_rows(
        _draft(),
        package_id="roleplay2026.camilly",
        script_version="200",
        frame_prefix="encontro",
        image_map={"encontro_001_descricao": "camilly1.webp", "encontro_001_camilly_pensamento_01": "camilly2.webp"},
    )
    assert rows[0]["image_id"] == "camilly1.webp"
    assert rows[1]["image_id"] == ""
    assert rows[2]["image_id"] == "camilly2.webp"


def test_image_name_is_webp_and_sequential() -> None:
    assert core.normalize_image_name("Camilly", 1) == "camilly1.webp"
    assert core.normalize_image_name("Casada frustrada", 12) == "casada_frustrada12.webp"


def test_csv_header_has_no_updated_at() -> None:
    rows = core.compile_rows(
        "[DESCRIÇÃO] Cena inicial.",
        package_id="roleplay2026.teste",
        script_version="1",
        frame_prefix="cena",
    )
    header = core.rows_to_csv(rows).splitlines()[0]
    assert header == "package_id,script_version,line_id,order,instruction,status,image_id"
    assert "updated_at" not in header
