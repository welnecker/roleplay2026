from __future__ import annotations

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


def test_politica_nao_limita_ponte_a_blocos_iniciais() -> None:
    script = _script()

    assert bridge_policy(script) == {"mode": "required"}


def test_todos_os_blocos_canonicos_do_card_aceitam_ponte() -> None:
    script = _script()
    canonical_beats = {
        beat_id: beat
        for beat_id, beat in script.beats.items()
        if str(beat.get("block_type", "canonical")) != "terminal_yard"
    }

    assert canonical_beats
    assert {str(beat.get("block_id", "")) for beat in canonical_beats.values()} >= {
        "encontro_acidental",
        "reencontro_fila",
        "motel",
    }
    assert all(bridge_enabled_for_beat(script, beat_id) for beat_id in canonical_beats)


def test_patio_terminal_continua_identificado_como_destino_estrutural() -> None:
    script = _script()
    yard_beats = {
        beat_id: beat
        for beat_id, beat in script.beats.items()
        if str(beat.get("block_type", "")) == "terminal_yard"
    }

    assert yard_beats
    assert all(str(beat.get("terminal_yard_id", "")) for beat in yard_beats.values())
