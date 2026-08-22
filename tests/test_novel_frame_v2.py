from __future__ import annotations

import json

from services.editorial_compiler import compile_editorial_document
from services.editorial_runtime import EditorialScript
from services.novel_frame_patch import (
    build_frame_prompt,
    compile_novel_frame_story,
    is_novel_frame_rows,
    render_frame_html,
)
from services.novel_v2_adapter import movement_from_script, next_movement_id


def _base_document() -> dict:
    return {
        "format_version": 3,
        "package_id": "roleplay2026.camilly",
        "script_version": "1",
        "introduction": "ABERTURA LEGADA QUE NÃO DEVE SER USADA",
        "character": {
            "name": "Camilly",
            "speech_style": [
                "português brasileiro natural",
                "fala sexual, direta e espontânea",
                "preserva as palavras e expressões fornecidas pelo roteiro",
            ],
        },
        "character_core": {
            "invariants": [
                "Pensamento e fala aparecem juntos na mesma resposta.",
                "Desejo, malícia e prazer fazem parte da personalidade.",
            ],
        },
        "blocks": [
            {
                "block_id": "legacy",
                "order": 1,
                "entry_beat_id": "legacy_001",
                "beats": [],
            }
        ],
    }


def _rows() -> list[dict]:
    return [
        {
            "line_id": "encontro_001_descricao",
            "order": 10,
            "instruction": "[DESCRIÇÃO] Camilly avista {{nome}} no carro e se aproxima.",
            "status": "active",
        },
        {
            "line_id": "encontro_001_camilly_fala",
            "order": 20,
            "instruction": "[FALA camilly] Eu cumprimento {{nome}} com surpresa e entusiasmo.",
            "status": "active",
        },
        {
            "line_id": "encontro_001_usuario_fala",
            "order": 30,
            "instruction": "[FALA usuario] Eu reconheço Camilly e a convido a se aproximar.",
            "status": "active",
        },
        {
            "line_id": "encontro_001_camilly_pensamento",
            "order": 40,
            "instruction": "[PENSAMENTO camilly] Quero aproveitar a coincidência sem mostrar toda a minha intenção.",
            "status": "active",
        },
        {
            "line_id": "encontro_001_usuario_pensamento",
            "order": 50,
            "instruction": "[PENSAMENTO usuario] Percebo que ela está especialmente animada.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_descricao",
            "order": 60,
            "instruction": "[DESCRIÇÃO] Camilly pede uma carona para a praia.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_camilly_fala",
            "order": 70,
            "instruction": "[FALA camilly] Eu peço a carona com naturalidade e confiança.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_usuario_fala",
            "order": 80,
            "instruction": "[FALA usuario] Eu aceito e a convido a entrar.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_camilly_pensamento",
            "order": 90,
            "instruction": "[PENSAMENTO camilly] A carona é útil, mas ficar sozinha com ele é ainda melhor.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_usuario_pensamento",
            "order": 100,
            "instruction": "[PENSAMENTO usuario] A companhia dela tornou o trajeto mais interessante.",
            "status": "active",
        },
        {
            "line_id": "encontro_003_descricao",
            "order": 110,
            "instruction": "[DESCRIÇÃO] Camilly entra e os dois seguem para a praia.",
            "status": "active",
        },
        {
            "line_id": "encontro_003_camilly_fala",
            "order": 120,
            "instruction": "[FALA camilly] Eu agradeço e noto como é bom estarmos sozinhos.",
            "status": "active",
        },
        {
            "line_id": "encontro_003_usuario_fala",
            "order": 130,
            "instruction": "[FALA usuario] Eu demonstro estar à vontade com a companhia dela.",
            "status": "active",
        },
        {
            "line_id": "encontro_003_camilly_pensamento",
            "order": 140,
            "instruction": "[PENSAMENTO camilly] Agora tenho alguns minutos sozinha com ele.",
            "status": "active",
        },
        {
            "line_id": "encontro_003_usuario_pensamento",
            "order": 150,
            "instruction": "[PENSAMENTO usuario] Ela parece mais solta e isso desperta minha curiosidade.",
            "status": "active",
        },
    ]


def test_detecta_formato_de_quadros_multipersonagem() -> None:
    assert is_novel_frame_rows(_rows()) is True


def test_compila_tres_quadros_na_ordem_da_planilha() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    block = document["blocks"][0]
    assert document["script_version"] == "200"
    assert document["authoring_source"] == "spreadsheet_novel_frame_v2"
    assert block["entry_beat_id"] == "encontro_001"
    assert [beat["beat_id"] for beat in block["beats"]] == [
        "encontro_001",
        "encontro_002",
        "encontro_003",
    ]
    assert block["beats"][0]["next_beat_id"] == "encontro_002"
    assert block["beats"][2]["next_beat_id"] == ""


def test_primeira_descricao_da_planilha_vira_abertura_e_substitui_introducao_legada() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    block = document["blocks"][0]
    assert block["scene_introduction"] == "Camilly avista {{nome}} no carro e se aproxima."
    compiled = compile_editorial_document(document)
    assert compiled["scene"]["introduction"] == "Camilly avista {{nome}} no carro e se aproxima."
    assert compiled["scene"]["introduction"] != document["introduction"]


def test_primeiro_quadro_nao_repete_descricao_ja_exibida_na_abertura() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_001")
    prefix = "NOVEL_FRAME_V2\n"
    payload = json.loads(movement.instruction[len(prefix):])
    assert payload["description"] == ""
    assert [(item["kind"], item["actor"]) for item in payload["entries"]] == [
        ("fala", "camilly"),
        ("fala", "usuario"),
        ("pensamento", "camilly"),
        ("pensamento", "usuario"),
    ]


def test_descricoes_dos_quadros_seguintes_permanecem_no_fluxo() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_002")
    prefix = "NOVEL_FRAME_V2\n"
    payload = json.loads(movement.instruction[len(prefix):])
    assert payload["description"] == "Camilly pede uma carona para a praia."


def test_quadro_carrega_contrato_editorial_de_voz_da_personagem() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_002")
    payload = json.loads(movement.instruction.removeprefix("NOVEL_FRAME_V2\n"))

    assert payload["voice_contract"]["speech_style"] == [
        "português brasileiro natural",
        "fala sexual, direta e espontânea",
        "preserva as palavras e expressões fornecidas pelo roteiro",
    ]
    assert "invariants" not in payload["voice_contract"]


def test_documento_de_quadros_continua_compativel_com_editorial_script() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    assert script.first_beat_id == "encontro_001"
    assert next_movement_id(script, "") == "encontro_001"
    assert next_movement_id(script, "encontro_001") == "encontro_002"
    assert next_movement_id(script, "encontro_002") == "encontro_003"
    assert next_movement_id(script, "encontro_003") == ""


def test_prompt_do_primeiro_quadro_nao_pede_descricao_repetida() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_001")
    prompt = build_frame_prompt(
        character_name="Camilly",
        user_name="Donisete",
        movement=movement,
    )
    assert "Donisete" in prompt
    assert "{{nome}}" not in prompt
    assert "A descrição deste quadro já foi exibida na abertura" in prompt
    assert "Não gere [DESCRIÇÃO] neste quadro" in prompt
    assert "A fala do protagonista também é roteirizada" in prompt
    assert "Cada PENSAMENTO contém um núcleo autoral obrigatório" in prompt
    assert "Não omita, não duplique e não acrescente nenhuma entry" in prompt
    assert '"voice_contract"' in prompt
    assert "fala sexual, direta e espontânea" in prompt
    assert "Pensamento e fala aparecem juntos" not in prompt
    assert "Preserve palavrões, gírias, risadas" in prompt
    assert "não autoriza higienizar, moralizar, amenizar" in prompt
    assert "correspondência exata de 1 para 1" in prompt
    assert "Nunca crie PENSAMENTO para acompanhar uma FALA" in prompt
    assert "não duplique e não acrescente nenhuma entry" in prompt


def test_prompt_preserva_intensidade_sem_ampliar_entry_neutra() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_001")
    prompt = build_frame_prompt(
        character_name="Camilly",
        user_name="Donisete",
        movement=movement,
    )

    assert "Preserve o grau de informalidade, vulgaridade, erotismo" in prompt
    assert "Não aumente gratuitamente a explicitude de uma entry neutra" in prompt
    assert "Se houver conflito entre embelezar a frase e preservar a voz autoral" in prompt


def test_prompt_da_vida_ao_pensamento_sem_alterar_fala_ou_inventar_fatos() -> None:
    document = compile_novel_frame_story(_base_document(), _rows(), script_version="200")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_001")
    prompt = build_frame_prompt(
        character_name="Camilly",
        user_name="Donisete",
        movement=movement,
    )

    assert "Cada PENSAMENTO contém um núcleo autoral obrigatório" in prompt
    assert "bom humor, malícia, erotismo, desejo, provocação" in prompt
    assert "não sexualize um pensamento neutro e não suavize um pensamento explícito" in prompt
    assert "apenas sentimentos, desejos, conflitos e estratégias do próprio actor" in prompt
    assert "Não invente fatos, ações, consentimento, excitação" in prompt
    assert "Nas FALAS, faça somente ajustes mínimos" in prompt
    assert "Nos PENSAMENTOS, preserve o núcleo autoral" in prompt


def test_sufixo_balao_e_preservado_com_nome_visivel_normal() -> None:
    rows = _rows()
    rows[1] = {
        **rows[1],
        "instruction": "[FALA camilly_balao] Porra, {{nome}}!!!",
    }
    document = compile_novel_frame_story(_base_document(), rows, script_version="201")
    script = EditorialScript(compile_editorial_document(document))
    movement = movement_from_script(script, "encontro_001")
    payload = json.loads(movement.instruction.removeprefix("NOVEL_FRAME_V2\n"))

    assert payload["entries"][0]["actor"] == "camilly_balao"

    prompt = build_frame_prompt(
        character_name="Camilly",
        user_name="Donisete",
        movement=movement,
    )
    assert '"actor": "camilly_balao"' in prompt
    assert '"visible_name": "Camilly"' in prompt
    assert "Camilly Balao" not in prompt
    assert "copie esse sufixo literalmente" in prompt


def test_renderer_separa_cena_falas_e_pensamentos() -> None:
    content = """[QUADRO encontro_002]
[DESCRIÇÃO]
Camilly reconhece Donisete no carro.
[FALA camilly|Camilly]
Oi, Donisete!
[FALA usuario|Donisete]
Oi, Camilly... chega mais.
[PENSAMENTO camilly|Camilly]
Essa coincidência pode render.
[PENSAMENTO usuario|Donisete]
Ela está animada demais para ser só simpatia.
[/QUADRO]"""
    rendered = render_frame_html(content, character_name="Camilly")
    assert rendered is not None
    assert ">Cena<" in rendered
    assert ">Camilly<" in rendered
    assert ">Donisete<" in rendered
    assert "pensamento" in rendered
    assert "Oi, Donisete!" in rendered
    assert "Oi, Camilly... chega mais." in rendered
