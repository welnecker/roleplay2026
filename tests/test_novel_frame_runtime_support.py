from __future__ import annotations

import json

from services.editorial_compiler import compile_editorial_document
from services.editorial_runtime import EditorialScript
from services.novel_frame_patch import compile_novel_frame_story
from services.novel_frame_runtime_support import first_frame_movement, is_frame_script
from services.novel_v2_adapter import next_movement_id
from services.story_profile import personalize_editorial_script


def _script() -> EditorialScript:
    base = {
        "format_version": 3,
        "package_id": "roleplay2026.camilly",
        "script_version": "1",
        "introduction": "INTRODUÇÃO ANTIGA QUE NÃO DEVE ABRIR O V2",
        "character": {"name": "Camilly"},
        "blocks": [],
    }
    rows = [
        {
            "line_id": "encontro_001_descricao",
            "order": 10,
            "instruction": "[DESCRIÇÃO] Camilly avista {{*nome}} no carro.",
            "status": "active",
        },
        {
            "line_id": "encontro_001_camilly_fala",
            "order": 20,
            "instruction": "[FALA camilly] Eu cumprimento {{nome}} e noto que {{**nome}} sorri.",
            "status": "active",
        },
        {
            "line_id": "encontro_001_usuario_fala",
            "order": 30,
            "instruction": "[FALA usuario] Eu convido Camilly a se aproximar.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_descricao",
            "order": 40,
            "instruction": "[DESCRIÇÃO] Camilly chega ao carro.",
            "status": "active",
        },
        {
            "line_id": "encontro_002_camilly_fala",
            "order": 50,
            "instruction": "[FALA camilly] Eu peço uma carona.",
            "status": "active",
        },
    ]
    document = compile_novel_frame_story(base, rows, script_version="200")
    return EditorialScript(compile_editorial_document(document))


def test_primeiro_quadro_recompoe_descricao_na_abertura() -> None:
    script = _script()
    assert is_frame_script(script)

    target_id, movement = first_frame_movement(script)

    assert target_id == "encontro_001"
    prefix = "NOVEL_FRAME_V2\n"
    assert movement.instruction.startswith(prefix)
    payload = json.loads(movement.instruction[len(prefix):])
    assert payload["description"] == "Camilly avista {{*nome}} no carro."
    assert [entry["kind"] for entry in payload["entries"]] == ["fala", "fala"]


def test_depois_da_abertura_o_proximo_quadro_e_encontro_002() -> None:
    script = _script()
    target_id, _ = first_frame_movement(script)

    assert next_movement_id(script, target_id) == "encontro_002"


def test_abertura_v2_nao_usa_introducao_antiga_do_pacote() -> None:
    script = _script()
    _, movement = first_frame_movement(script)

    assert "INTRODUÇÃO ANTIGA" not in movement.instruction
    assert "Camilly avista" in movement.instruction


def test_quadro_v2_personaliza_artigo_e_pronome_sem_mutar_snapshot() -> None:
    source = _script()
    personalized = personalize_editorial_script(
        source,
        {"preferred_name": "Ana", "story_gender": "Como mulher"},
    )

    _, movement = first_frame_movement(personalized)
    payload = json.loads(movement.instruction.removeprefix("NOVEL_FRAME_V2\n"))
    assert payload["description"] == "Camilly avista a Ana no carro."
    assert payload["entries"][0]["instruction"] == (
        "Eu cumprimento Ana e noto que ela sorri."
    )

    _, original_movement = first_frame_movement(source)
    assert "{{*nome}}" in original_movement.instruction
    assert "{{**nome}}" in original_movement.instruction


def test_personalizacao_de_quadros_fica_isolada_por_usuario() -> None:
    source = _script()
    male = personalize_editorial_script(
        source,
        {"preferred_name": "Janio", "story_gender": "Como homem"},
    )
    neutral = personalize_editorial_script(
        source,
        {"preferred_name": "Alex", "story_gender": "De forma neutra"},
    )

    _, male_movement = first_frame_movement(male)
    _, neutral_movement = first_frame_movement(neutral)
    assert "o Janio" in male_movement.instruction
    assert "ele sorri" in male_movement.instruction
    assert "Alex no carro" in neutral_movement.instruction
    assert "Alex sorri" in neutral_movement.instruction
