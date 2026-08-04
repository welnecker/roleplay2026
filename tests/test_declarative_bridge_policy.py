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


def test_card_real_carrega_politica_global_sem_registro_por_package_id() -> None:
    assert bridge_policy(_script()) == {"mode": "required"}


def test_card_real_ativa_supermercado_mensagens_video_e_motel() -> None:
    script = _script()

    assert bridge_enabled_for_beat(script, "encontro_acidental_001") is True
    assert bridge_enabled_for_beat(script, "reencontro_fila_001") is True
    assert bridge_enabled_for_beat(script, "mensagens_iniciais_001") is True
    assert bridge_enabled_for_beat(script, "video_001") is True
    assert bridge_enabled_for_beat(script, "motel_001") is True
