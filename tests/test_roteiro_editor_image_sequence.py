from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "roteiro_editor_desktop"
    / "image_sequence.py"
)
spec = importlib.util.spec_from_file_location("image_sequence", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_next_number_uses_mapping_when_source_path_could_not_be_restored() -> None:
    assert (
        module.next_image_number(
            "camilly",
            1,
            image_source_ids=(),
            mapped_image_ids=("camilly20.webp",),
        )
        == 21
    )


def test_next_number_considers_sources_mappings_and_description_bindings() -> None:
    assert (
        module.next_image_number(
            "camilly",
            4,
            image_source_ids=("camilly8.webp",),
            mapped_image_ids=("camilly12.webp",),
            binding_image_ids=("camilly10.webp",),
        )
        == 13
    )
