from __future__ import annotations

from pathlib import Path

from packages.loader import discover_packages, load_manifest


VALID_MANIFEST = """
format_version: 1
package_id: example.story
version: 1.0.0
author:
  name: Example Author
entrypoint: story.yaml
card:
  title: Example Story
  genres: [Drama]
commerce:
  access: free
"""


def create_package(root: Path, folder: str = "example") -> Path:
    package_root = root / folder
    package_root.mkdir()
    (package_root / "manifest.yaml").write_text(VALID_MANIFEST, encoding="utf-8")
    (package_root / "story.yaml").write_text("story_id: example\n", encoding="utf-8")
    return package_root


def test_load_manifest(tmp_path: Path) -> None:
    package_root = create_package(tmp_path)
    package = load_manifest(package_root / "manifest.yaml")

    assert package.manifest.package_id == "example.story"
    assert package.manifest.card.title == "Example Story"
    assert package.root == package_root.resolve()


def test_discover_packages_reports_invalid_package(tmp_path: Path) -> None:
    create_package(tmp_path)
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "manifest.yaml").write_text("package_id: ???\n", encoding="utf-8")

    packages, errors = discover_packages(tmp_path)

    assert [item.manifest.package_id for item in packages] == ["example.story"]
    assert len(errors) == 1
