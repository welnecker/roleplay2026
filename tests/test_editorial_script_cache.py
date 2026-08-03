from __future__ import annotations

from pathlib import Path
from types import ModuleType

from packages.loader import discover_packages
import services.editorial_script_cache as script_cache


class _CachedLoader:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1


def _installed_package():
    packages, errors = discover_packages(Path("installed_stories"))
    assert errors == []
    return next(
        package
        for package in packages
        if package.manifest.package_id == "roleplay2026.casada_frustrada"
    )


def test_fingerprint_considera_manifesto_e_extensoes() -> None:
    package = _installed_package()

    first = script_cache.editorial_package_fingerprint(package)
    second = script_cache.editorial_package_fingerprint(package)

    assert first == second
    assert len(first) == 64


def test_cache_e_invalidado_somente_quando_fingerprint_muda(monkeypatch) -> None:
    runtime = ModuleType("runtime_for_test")
    runtime.PACKAGE = _installed_package()
    runtime.load_script = _CachedLoader()

    fingerprints = iter(("version-a", "version-a", "version-b"))
    monkeypatch.setattr(
        script_cache,
        "editorial_package_fingerprint",
        lambda package: next(fingerprints),
    )

    assert script_cache.refresh_loaded_editorial_script_cache(runtime) is True
    assert runtime.load_script.clear_calls == 1

    assert script_cache.refresh_loaded_editorial_script_cache(runtime) is False
    assert runtime.load_script.clear_calls == 1

    assert script_cache.refresh_loaded_editorial_script_cache(runtime) is True
    assert runtime.load_script.clear_calls == 2
