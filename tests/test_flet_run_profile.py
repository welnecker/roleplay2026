from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

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


def test_consulta_recupera_perfil_sem_carregar_roteiro() -> None:
    service = object.__new__(FletRunService)
    service._lock = lambda *_args, **_kwargs: nullcontext()  # type: ignore[method-assign]
    service.repository = SimpleNamespace(
        get_active_run=lambda **_kwargs: SimpleNamespace(run_id="run_1"),
        list_interactions=lambda **_kwargs: [
            {
                "role": "assistant",
                "immersive_profile": {
                    "preferred_name": "Janio",
                    "story_gender": "Como homem",
                },
            }
        ],
    )

    profile = service.profile(
        account=SimpleNamespace(user_id="user_1", display_name="Conta"),
        package_id="story_1",
    )

    assert profile.completed is True
    assert profile.preferred_name == "Janio"
    assert profile.story_gender == "Como homem"


def test_run_nova_sem_perfil_solicita_onboarding() -> None:
    service = object.__new__(FletRunService)
    service._lock = lambda *_args, **_kwargs: nullcontext()  # type: ignore[method-assign]
    service.repository = SimpleNamespace(get_active_run=lambda **_kwargs: None)

    profile = service.profile(
        account=SimpleNamespace(user_id="user_1", display_name="Pessoa"),
        package_id="story_1",
    )

    assert profile.completed is False
    assert profile.preferred_name == "Pessoa"
    assert profile.story_gender == ""


def test_run_antiga_grava_perfil_no_quadro_atual_ao_reabrir() -> None:
    service = object.__new__(FletRunService)
    service._lock = lambda *_args, **_kwargs: nullcontext()  # type: ignore[method-assign]
    saved: list[dict[str, object]] = []
    service.repository = SimpleNamespace(
        persist_run_profile=lambda **kwargs: saved.append(kwargs),
    )
    context = SimpleNamespace(run=SimpleNamespace(run_id="run_1"))
    messages: list[dict[str, object]] = [
        {"role": "assistant", "content": "[QUADRO quadro_1]\n[/QUADRO]"}
    ]
    service._load = (  # type: ignore[method-assign]
        lambda account, package_id, *, requested_profile: (
            SimpleNamespace(),
            SimpleNamespace(),
            SimpleNamespace(user_id=account.user_id),
            context,
            SimpleNamespace(),
            messages,
            requested_profile,
        )
    )
    service._view = lambda *_args: "quadro"  # type: ignore[method-assign]

    result = service.open(
        account=SimpleNamespace(user_id="user_1"),
        package_id="story_1",
        preferred_name="Janio",
        story_gender="Como homem",
    )

    assert result == "quadro"
    assert saved[0]["run_id"] == "run_1"
    assert saved[0]["profile"] == {
        "preferred_name": "Janio",
        "story_gender": "Como homem",
    }
    assert messages[0]["immersive_profile"] == saved[0]["profile"]
