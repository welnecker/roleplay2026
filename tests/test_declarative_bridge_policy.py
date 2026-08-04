from pathlib import Path

from packages.loader import discover_packages
from services.editorial_bridge import bridge_enabled_for_beat, bridge_policy
from services.editorial_package_loader import compile_editorial_package


ROOT = Path("installed_stories")
PACKAGE_ID = "roleplay2026.casada_frustrada"


def _script():
    packages, errors = discover_packages(ROOT)
    assert errors == []
    package = next(item for item in packages if item.manifest.package_id == PACKAGE_ID)
    return compile_editorial_package(package)


def test_card_real_carrega_politica_sem_registro_por_package_id() -> None:
    script = _script()

    assert bridge_policy(script) == {
        "mode": "required",
        "block_ids": ["encontro_acidental", "reencontro_fila"],
        "exclude_block_ids": [
            "yard_help_refused",
            "yard_invasive_approach",
            "motel",
        ],
    }


def test_card_real_ativa_supermercado_e_exclui_motel() -> None:
    script = _script()

    assert bridge_enabled_for_beat(script, "encontro_acidental_001") is True
    assert bridge_enabled_for_beat(script, "reencontro_fila_001") is True
    assert bridge_enabled_for_beat(script, "motel_001") is False
