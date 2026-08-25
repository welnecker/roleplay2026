from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "roteiro_editor_desktop"
    / "project_image_restore.py"
)
spec = importlib.util.spec_from_file_location("project_image_restore", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_restore_keeps_existing_original_image_sources(tmp_path: Path) -> None:
    source = tmp_path / "originais" / "foto.jpg"
    source.parent.mkdir()
    source.write_bytes(b"imagem")
    project = tmp_path / "roteiro.json"

    payload = {
        "image_map": {"cena_001_descricao": "camilly1.webp"},
        "image_sources": {"camilly1.webp": str(source)},
        "reference_files": [str(source)],
        "reference_index": 0,
        "description_bindings": {
            "1": {"source": str(source), "image_id": "camilly1.webp"}
        },
    }

    restored = module.restore_project_image_state(payload, project_path=project)

    assert restored["image_sources"]["camilly1.webp"] == str(source)
    assert restored["reference_files"] == [str(source)]
    assert restored["description_bindings"]["1"]["source"] == str(source)


def test_restore_recovers_exported_images_when_original_paths_are_stale(tmp_path: Path) -> None:
    project_dir = tmp_path / "historia_pronto"
    images_dir = project_dir / "imagens"
    images_dir.mkdir(parents=True)
    exported = images_dir / "mary1.webp"
    exported.write_bytes(b"imagem")
    project = project_dir / "projeto_roteiro.json"

    payload = {
        "image_map": {"encontro_001_descricao": "mary1.webp"},
        "image_sources": {"mary1.webp": "C:/pasta-antiga/foto.png"},
        "reference_files": ["C:/pasta-antiga/foto.png"],
        "reference_index": 9,
        "description_bindings": {
            "1": {"source": "C:/pasta-antiga/foto.png", "image_id": "mary1.webp"}
        },
    }

    restored = module.restore_project_image_state(payload, project_path=project)

    assert restored["image_sources"]["mary1.webp"] == str(exported)
    assert restored["reference_files"] == [str(exported)]
    assert restored["reference_index"] == 0
    assert restored["description_bindings"]["1"]["source"] == str(exported)


def test_restore_supports_older_project_with_image_map_but_no_sources(tmp_path: Path) -> None:
    project_dir = tmp_path / "projeto"
    images_dir = project_dir / "imagens"
    images_dir.mkdir(parents=True)
    recovered = images_dir / "camilly2.webp"
    recovered.write_bytes(b"imagem")
    project = project_dir / "projeto_roteiro.json"

    payload = {
        "image_map": {"encontro_001_camilly_fala_01": "camilly2.webp"},
        "image_sources": {},
        "reference_files": [],
        "reference_index": -1,
    }

    restored = module.restore_project_image_state(payload, project_path=project)

    assert restored["image_sources"] == {"camilly2.webp": str(recovered)}
    assert restored["reference_files"] == [str(recovered)]
    assert restored["reference_index"] == 0
