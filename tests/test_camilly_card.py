from __future__ import annotations

from pathlib import Path

from packages.loader import discover_packages
from platform_core.catalog import load_catalog
from services.editorial_package_loader import compile_editorial_package


ROOT = Path(__file__).resolve().parents[1]
INSTALLED_STORIES = ROOT / "installed_stories"


def test_camilly_aparece_no_catalogo_com_runtime_editorial_pago() -> None:
    cards, errors = load_catalog(INSTALLED_STORIES)

    assert errors == []
    card = next(item for item in cards if item.package_id == "roleplay2026.camilly")
    assert card.title == "Camilly"
    assert card.profile_name == "Camilly"
    assert card.price_label == "R$ 9,90"
    assert card.replay_requires_purchase is True


def test_camilly_compila_sem_depender_da_planilha() -> None:
    packages, errors = discover_packages(INSTALLED_STORIES)

    assert errors == []
    package = next(
        item for item in packages if item.manifest.package_id == "roleplay2026.camilly"
    )
    script = compile_editorial_package(package)
    assert script.raw["character"]["name"] == "Camilly"
    assert script.first_beat_id == "camilly_fallback_001"
