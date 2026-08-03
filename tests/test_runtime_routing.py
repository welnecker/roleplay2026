from __future__ import annotations

from pathlib import Path

from packages.models import InstalledStoryPackage, StoryPackageManifest
from platform_core.runtime_routing import player_page_for, runtime_route_for


def _package(kind: str) -> InstalledStoryPackage:
    runtime: dict[str, object] = {"kind": kind}
    if kind == "editorial":
        runtime["editorial"] = {"source": "editorial.yaml"}

    manifest = StoryPackageManifest.model_validate(
        {
            "format_version": 2,
            "package_id": f"example.{kind}",
            "version": "1.0.0",
            "author": {"name": "Example"},
            "entrypoint": "story.yaml",
            "runtime": runtime,
            "card": {"title": f"Example {kind}"},
            "commerce": {"access": "free"},
        }
    )
    root = Path("/tmp") / f"example-{kind}"
    return InstalledStoryPackage(
        root=root,
        manifest_path=root / "manifest.yaml",
        manifest=manifest,
    )


def test_editorial_usa_player_generico() -> None:
    package = _package("editorial")

    route = runtime_route_for(package)

    assert route.kind == "editorial"
    assert route.page == "pages/2_Historia_Editorial.py"
    assert player_page_for(package) == route.page


def test_roteamento_nao_depende_do_package_id() -> None:
    first = _package("editorial")
    second_manifest = first.manifest.model_copy(
        update={"package_id": "another.story"}
    )
    second = first.model_copy(update={"manifest": second_manifest})

    assert player_page_for(first) == player_page_for(second)


def test_runtime_simples_permanece_no_player_principal() -> None:
    assert player_page_for(_package("simple")) == "app.py"


def test_roteador_nao_conhece_historia_especifica() -> None:
    source = Path("platform_core/runtime_routing.py").read_text(encoding="utf-8")

    assert "casada_frustrada" not in source
    assert "roleplay2026." not in source
