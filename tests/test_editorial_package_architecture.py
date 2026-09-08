from __future__ import annotations

from pathlib import Path

import pytest

from packages.loader import load_manifest
from services.editorial_package_loader import (
    EditorialPackageError,
    load_editorial_document,
)


def _write_package(root: Path, *, source: str = "editorial.yaml"):
    package_root = root / "story"
    package_root.mkdir()
    (package_root / "manifest.yaml").write_text(
        f"""
format_version: 2
package_id: example.editorial
version: 1.0.0
author:
  name: Example
entrypoint: story.yaml
runtime:
  kind: editorial
  editorial:
    source: {source}
    extensions:
      - extension.yaml
card:
  title: Example
commerce:
  access: free
""",
        encoding="utf-8",
    )
    (package_root / "story.yaml").write_text("story_id: compatibility\n", encoding="utf-8")
    (package_root / "editorial.yaml").write_text(
        """
format_version: 2
package_id: example.editorial
script_version: 1.0.0
character:
  character_id: character
  name: Character
blocks:
  - block_id: opening
    order: 1
    entry_beat_id: opening_001
    beats:
      - beat_id: opening_001
        canonical_line: Oi.
        on_user: {}
memories: []
endings: []
""",
        encoding="utf-8",
    )
    (package_root / "extension.yaml").write_text(
        """
patch_beats:
  opening_001:
    response_boundary: integrated_canonical
""",
        encoding="utf-8",
    )
    return load_manifest(package_root / "manifest.yaml")


def test_manifesto_declara_runtime_editorial() -> None:
    root = Path(__file__).resolve().parent.parent
    package = load_manifest(root / "installed_stories" / "casada_frustrada" / "manifest.yaml")
    runtime = package.manifest.runtime
    assert runtime.kind == "editorial"
    assert runtime.editorial is not None
    assert runtime.editorial.source == "content/editorial.yaml"
    assert runtime.editorial.extensions == (
        "content/extensions/continuation.yaml",
        "content/extensions/narrative.yaml",
        "content/extensions/opening_flow.yaml",
        "content/extensions/story.yaml",
        "content/extensions/fixes.yaml",
        "content/extensions/guardrails.yaml",
        "content/extensions/transitions.yaml",
        "content/extensions/parking_dialogue.yaml",
        "content/extensions/dynamic_endings.yaml",
        "content/extensions/character_path.yaml",
        "content/extensions/runtime.yaml",
    )


def test_card_canonico_possui_conteudo_autocontido() -> None:
    root = Path(__file__).resolve().parent.parent
    package_root = root / "installed_stories" / "casada_frustrada"
    package = load_manifest(package_root / "manifest.yaml")
    editorial = package.manifest.runtime.editorial
    assert editorial is not None
    declared_files = (editorial.source, *editorial.extensions)
    assert all((package_root / relative_path).is_file() for relative_path in declared_files)

    obsolete_files = (
        "supermarket_pilot.yaml",
        "supermarket_continuation.yaml",
        "narrative_enhancements.yaml",
        "full_story.yaml",
        "full_story_fixes.yaml",
        "personality_guardrails.yaml",
    )
    assert all(not (package_root / filename).exists() for filename in obsolete_files)


def test_carregador_aplica_extensoes_declaradas_no_manifesto(tmp_path: Path) -> None:
    package = _write_package(tmp_path)
    document = load_editorial_document(package)
    beat = document["blocks"][0]["beats"][0]
    assert beat["response_boundary"] == "integrated_canonical"


def test_carregador_rejeita_arquivo_fora_do_pacote(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text("{}", encoding="utf-8")
    package = _write_package(tmp_path, source="../outside.yaml")
    with pytest.raises(EditorialPackageError, match="fora da pasta"):
        load_editorial_document(package)
