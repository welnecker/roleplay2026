from __future__ import annotations

import pytest

from flet_api.runs import FletRunService


def test_perfil_solicitado_e_completo_para_personalizar_roteiro() -> None:
    profile = FletRunService._requested_profile(
        preferred_name="  Janio  ",
        story_gender="Como homem",
    )

    assert profile == {
        "preferred_name": "Janio",
        "name": "Janio",
        "user_name": "Janio",
        "story_gender": "Como homem",
        "completed": True,
        "stage": 3,
    }


@pytest.mark.parametrize(
    ("preferred_name", "story_gender"),
    [
        ("", "Como homem"),
        ("Janio", ""),
        ("Janio", "Masculino"),
    ],
)
def test_perfil_incompleto_ou_invalido_e_recusado(
    preferred_name: str,
    story_gender: str,
) -> None:
    with pytest.raises(ValueError):
        FletRunService._requested_profile(
            preferred_name=preferred_name,
            story_gender=story_gender,
        )


def test_perfil_persistido_na_run_continua_sendo_autoridade() -> None:
    requested = FletRunService._requested_profile(
        preferred_name="Outro nome",
        story_gender="De forma neutra",
    )
    recovered = FletRunService._profile(
        [
            {
                "role": "assistant",
                "immersive_profile": {
                    "preferred_name": "Ana",
                    "story_gender": "Como mulher",
                },
            }
        ],
        requested,
    )

    assert recovered["preferred_name"] == "Ana"
    assert recovered["story_gender"] == "Como mulher"
