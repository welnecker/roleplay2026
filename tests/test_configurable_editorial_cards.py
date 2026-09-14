from __future__ import annotations

from packages.loader import discover_packages
from services.editorial_content import find_editorial_package
from services.editorial_package_loader import load_editorial_document


def test_degustacao_is_discovered_as_an_editorial_package() -> None:
    package = find_editorial_package("roleplay2026.degustacao")

    assert package is not None
    assert package.manifest.runtime.kind == "editorial"
    assert package.manifest.commerce.access == "free"
    document = load_editorial_document(package)
    assert document["package_id"] == "roleplay2026.degustacao"
    assert document["character"]["character_id"] == "camilly"


def test_all_valid_editorial_cards_are_discovered_without_an_allowlist() -> None:
    packages, errors = discover_packages(
        __import__("services.editorial_content", fromlist=["INSTALLED_STORIES_ROOT"]).INSTALLED_STORIES_ROOT
    )

    assert errors == []
    expected = {
        package.manifest.package_id
        for package in packages
        if package.manifest.runtime.kind == "editorial"
    }
    discovered = {
        package.manifest.package_id
        for package in packages
        if find_editorial_package(package.manifest.package_id) is not None
    }
    assert discovered == expected
    assert "roleplay2026.degustacao" in discovered
