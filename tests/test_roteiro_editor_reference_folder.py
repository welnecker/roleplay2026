from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "roteiro_editor_desktop"
    / "reference_folder.py"
)
spec = importlib.util.spec_from_file_location("reference_folder", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_lists_supported_images_from_selected_directory(tmp_path: Path) -> None:
    for name in ("cena10.JPG", "cena02.png", "cena03.webp", "notas.txt"):
        (tmp_path / name).write_bytes(b"arquivo")

    result = module.reference_images_from_directory(tmp_path)

    assert [Path(item).name for item in result] == [
        "cena02.png",
        "cena03.webp",
        "cena10.JPG",
    ]


def test_saved_reference_directory_has_priority() -> None:
    payload = {
        "reference_directory": "D:/Minha Historia/Imagens",
        "reference_files": ["C:/antiga/cena.png"],
    }
    assert module.reference_directory_from_project(payload) == "D:/Minha Historia/Imagens"


def test_old_project_infers_common_reference_directory() -> None:
    payload = {
        "reference_files": ["C:/roteiro/imagens/cena1.png", "C:/roteiro/imagens/cena2.png"],
        "image_sources": {"cena3.webp": "C:/roteiro/imagens/cena3.png"},
    }
    assert Path(module.reference_directory_from_project(payload)) == Path(
        "C:/roteiro/imagens"
    )
