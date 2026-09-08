from __future__ import annotations

from pathlib import Path

import pytest

from packages.loader import discover_packages
from services.story_cast import cast_profile, default_cast_names, normalize_cast_names


INSTALLED_STORIES = Path(__file__).resolve().parent.parent / "installed_stories"


def _manifest():
    packages, errors = discover_packages(INSTALLED_STORIES)
    assert errors == []
    return next(
        package.manifest
        for package in packages
        if package.manifest.package_id == "roleplay2026.casada_frustrada"
    )


def test_elenco_usa_nomes_autorais_como_padrao() -> None:
    assert default_cast_names(_manifest()) == {"mary": "Mary", "usuario": "Doni"}


def test_elenco_aceita_troca_parcial_e_completa_os_demais_papeis() -> None:
    assert normalize_cast_names(_manifest(), {"mary": "Sandra"}) == {
        "mary": "Sandra",
        "usuario": "Doni",
    }


def test_perfil_de_elenco_preserva_compatibilidade_com_motor_atual() -> None:
    profile = cast_profile(_manifest(), {"mary": "Sandra", "usuario": "Edu"})

    assert profile["identity_mode"] == "cast"
    assert profile["cast_names"] == {"mary": "Sandra", "usuario": "Edu"}
    assert profile["cast_default_names"] == {"mary": "Mary", "usuario": "Doni"}
    assert profile["preferred_name"] == "Edu"
    assert profile["story_gender"] == "Como homem"


@pytest.mark.parametrize(
    "names",
    [
        {"mary": "Sandra", "usuario": "sandra"},
        {"desconhecido": "Alex"},
        {"mary": ""},
    ],
)
def test_elenco_recusa_nomes_ambiguos_ou_papeis_invalidos(names: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        normalize_cast_names(_manifest(), names)
