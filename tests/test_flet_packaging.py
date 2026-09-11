from __future__ import annotations

import ast
import struct
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _config() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _png_size(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", payload[16:24])


def test_standalone_client_has_stable_identity_and_minimal_dependencies() -> None:
    config = _config()
    project = config["project"]
    flet = config["tool"]["flet"]

    assert project["name"] == "entrecenas-roleplay"
    assert project["requires-python"] == ">=3.12,<3.13"
    assert project["dependencies"] == [
        "flet==0.86.5",
        "flet-secure-storage==0.86.5",
        "requests>=2.32,<3",
    ]
    assert flet["bundle_id"] == "br.com.entrecenas.roleplay"
    assert flet["app"]["module"] == "main.py"
    assert flet["android"]["target_sdk_version"] == 36


def test_standalone_client_excludes_server_data_and_secrets() -> None:
    excluded = set(_config()["tool"]["flet"]["app"]["exclude"])

    assert {
        ".env",
        ".streamlit",
        "billing",
        "flet_api",
        "installed_stories",
        "narrative_v2",
        "persistence",
        "platform_core",
        "services",
    } <= excluded

    client_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "flet_client").glob("*.py")
    )
    assert "platform_core" not in client_source


def test_standalone_client_does_not_import_excluded_server_packages() -> None:
    excluded_packages = {
        item.split("/", maxsplit=1)[0]
        for item in _config()["tool"]["flet"]["app"]["exclude"]
        if "." not in item
    }
    imported_packages: set[str] = set()

    for path in [ROOT / "main.py", *(ROOT / "flet_client").glob("*.py")]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_packages.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_packages.add(node.module.split(".", maxsplit=1)[0])

    assert imported_packages.isdisjoint(excluded_packages)


def test_standalone_client_icons_have_native_build_sizes() -> None:
    assert _png_size(ROOT / "assets" / "icon.png") == (1024, 1024)
    assert _png_size(ROOT / "assets" / "icon_android.png") == (1024, 1024)
    assert _png_size(ROOT / "assets" / "icon_windows.png") == (256, 256)
