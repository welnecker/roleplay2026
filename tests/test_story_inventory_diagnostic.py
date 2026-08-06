from __future__ import annotations

import json
from pathlib import Path

from packages.loader import discover_packages
from services.editorial_package_loader import compile_editorial_package


def test_print_compiled_story_inventory() -> None:
    packages, errors = discover_packages(Path("installed_stories"))
    assert errors == []
    package = next(
        item
        for item in packages
        if item.manifest.package_id == "roleplay2026.casada_frustrada"
    )
    script = compile_editorial_package(package)

    beats = script.beats
    bridge_ids = sorted(
        beat_id
        for beat_id, beat in beats.items()
        if str(beat.get("type", "") or "").strip().lower() == "bridge"
    )
    canonical_ids = sorted(set(beats) - set(bridge_ids))

    raw_blocks = [
        block
        for block in script.raw.get("blocks", []) or []
        if isinstance(block, dict)
    ]
    block_inventory = []
    for block in raw_blocks:
        declared = [
            beat
            for beat in block.get("beats", []) or []
            if isinstance(beat, dict)
        ]
        block_inventory.append(
            {
                "block_id": str(block.get("block_id", "")),
                "beats": len(declared),
                "bridges": sum(
                    1
                    for beat in declared
                    if str(beat.get("type", "") or "").strip().lower() == "bridge"
                ),
            }
        )

    inventory = {
        "total_compiled_beats": len(beats),
        "canonical_beats": len(canonical_ids),
        "declared_bridge_beats": len(bridge_ids),
        "ending_nodes": len(script.endings),
        "blocks": len(raw_blocks),
        "bridge_ids": bridge_ids,
        "block_inventory": block_inventory,
    }
    print("STORY_INVENTORY=" + json.dumps(inventory, ensure_ascii=False, sort_keys=True))

    assert len(beats) == len(canonical_ids) + len(bridge_ids)
