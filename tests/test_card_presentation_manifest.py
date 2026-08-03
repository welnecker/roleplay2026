from pathlib import Path

import pytest

from packages.loader import discover_packages
from packages.models import PackageCommerce
from platform_core.catalog import package_to_story_card


INSTALLED_STORIES = Path(__file__).resolve().parent.parent / "installed_stories"


def _casada_frustrada():
    packages, errors = discover_packages(INSTALLED_STORIES)
    assert errors == []
    return next(
        package
        for package in packages
        if package.manifest.package_id == "roleplay2026.casada_frustrada"
    )


def test_perfil_do_card_vem_do_manifesto() -> None:
    package = _casada_frustrada()
    profile = package.manifest.card.character_profile
    assert profile is not None

    card = package_to_story_card(package)

    assert card.profile_name == "Mary"
    assert card.profile_identity == profile.identity
    assert card.profile_personality == profile.personality
    assert card.profile_intention == profile.intention


def test_replay_pago_e_declarado_sem_package_id_especial() -> None:
    package = _casada_frustrada()
    card = package_to_story_card(package)

    assert package.manifest.commerce.replay_policy == "new_purchase"
    assert card.replay_requires_purchase is True

    source = Path("ui_components.py").read_text(encoding="utf-8")
    assert "casada_frustrada" not in source
    assert "_PILOT_PACKAGE_ID" not in source
    assert "story.replay_requires_purchase" in source


def test_politica_de_replay_rejeita_valor_desconhecido() -> None:
    with pytest.raises(ValueError, match="replay_policy"):
        PackageCommerce.model_validate(
            {
                "access": "paid",
                "price_cents": 990,
                "replay_policy": "special_story_rule",
            }
        )
