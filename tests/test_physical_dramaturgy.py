from __future__ import annotations

import pytest

from services.editorial_content import load_source_document
from services.editorial_physical_dramaturgy import (
    render_physical_dramaturgy,
    select_physical_dramaturgy,
)
from services.editorial_runtime_impl import PilotState


def test_card_declara_funcoes_dramaticas_para_o_perfil_fisico() -> None:
    document = load_source_document()
    policy = document["physical_dramaturgy"]

    assert policy["max_active_aspects"] == 1
    assert set(policy["aspects"]) == {
        "hair_as_social_presence",
        "green_eyes_as_relational_risk",
        "curves_as_self_awareness",
        "adult_brazilian_embodiment",
    }
    profile = set(document["character"]["physical_profile"])
    assert all(item["trait"] in profile for item in policy["aspects"].values())


def test_corpo_curvilineo_so_entra_quando_video_desejo_e_confianca_autorizam() -> None:
    document = load_source_document()
    target = {"beat_id": "video_002", "block_id": "video"}
    context = "Mary decide como aparecer na câmera e quanto do próprio corpo deseja mostrar."

    low = PilotState(trust=4, desire=7)
    assert select_physical_dramaturgy(document, low, target, context, "engaged") == []

    ready = PilotState(trust=7, desire=7)
    selected = select_physical_dramaturgy(document, ready, target, context, "engaged")
    assert [item.aspect_id for item in selected] == ["curves_as_self_awareness"]
    assert "controle" in selected[0].dramatic_function


def test_olhar_funciona_como_risco_relacional_sem_inventar_sentimento_do_usuario() -> None:
    document = load_source_document()
    state = PilotState(trust=6)
    target = {"beat_id": "video_001", "block_id": "video"}

    selected = select_physical_dramaturgy(
        document,
        state,
        target,
        "Mary entra no vídeo e encara a câmera com mais verdade.",
        "engaged",
    )
    prompt = render_physical_dramaturgy(selected)

    assert [item.aspect_id for item in selected] == ["green_eyes_as_relational_risk"]
    assert "medida de risco relacional" in prompt
    assert "Não descreva ações do usuário" in prompt
    assert "green_eyes_as_relational_risk" not in prompt
    assert "olhos verdes" not in prompt


def test_mesmo_aspecto_e_despriorizado_no_turno_seguinte_quando_ha_alternativa() -> None:
    document = {
        "character": {"physical_profile": ["traço A", "traço B"]},
        "physical_dramaturgy": {
            "max_active_aspects": 1,
            "aspects": {
                "a": {
                    "trait": "traço A",
                    "priority": 10,
                    "dramatic_function": "Função A.",
                },
                "b": {
                    "trait": "traço B",
                    "priority": 5,
                    "dramatic_function": "Função B.",
                },
            },
        },
    }
    state = PilotState()
    target = {"beat_id": "beat_001"}

    first = select_physical_dramaturgy(document, state, target, "", "engaged")
    second = select_physical_dramaturgy(document, state, target, "", "engaged")

    assert [item.aspect_id for item in first] == ["a"]
    assert [item.aspect_id for item in second] == ["b"]


def test_motor_rejeita_traco_que_nao_existe_no_perfil_canonico() -> None:
    document = {
        "character": {"physical_profile": ["cabelos castanhos"]},
        "physical_dramaturgy": {
            "aspects": {
                "invented": {
                    "trait": "olhos azuis",
                    "dramatic_function": "Usar o olhar.",
                }
            }
        },
    }

    with pytest.raises(ValueError, match="traço ausente"):
        select_physical_dramaturgy(
            document,
            PilotState(),
            {"beat_id": "beat_001"},
            "",
            "engaged",
        )
