from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "roteiro_editor_desktop"
    / "reference_gallery_allocation.py"
)
spec = importlib.util.spec_from_file_location("reference_gallery_allocation", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_archive_and_restore_reference(tmp_path: Path) -> None:
    source = tmp_path / "referencias" / "cena01.png"
    source.parent.mkdir()
    source.write_bytes(b"imagem")

    archived, original = module.archive_reference(source)

    assert original == source
    assert archived == source.parent / module.ARCHIVE_DIR_NAME / source.name
    assert archived.exists()
    assert not source.exists()
    assert module.is_archived_reference(archived)

    restored = module.restore_reference(archived, original)

    assert restored == source
    assert source.exists()
    assert not archived.exists()


def test_restore_never_overwrites_existing_reference(tmp_path: Path) -> None:
    gallery = tmp_path / "referencias"
    archive = gallery / module.ARCHIVE_DIR_NAME
    archive.mkdir(parents=True)
    archived = archive / "cena.png"
    archived.write_bytes(b"atribuida")
    existing = gallery / "cena.png"
    existing.write_bytes(b"nova")

    restored = module.restore_reference(archived, existing)

    assert restored == gallery / "cena_2.png"
    assert restored.read_bytes() == b"atribuida"
    assert existing.read_bytes() == b"nova"


def test_archive_uses_safe_name_when_archive_already_contains_file(tmp_path: Path) -> None:
    gallery = tmp_path / "referencias"
    archive = gallery / module.ARCHIVE_DIR_NAME
    archive.mkdir(parents=True)
    (archive / "cena.webp").write_bytes(b"antiga")
    source = gallery / "cena.webp"
    source.write_bytes(b"nova")

    archived, original = module.archive_reference(source)

    assert original == source
    assert archived == archive / "cena_2.webp"
    assert archived.read_bytes() == b"nova"
