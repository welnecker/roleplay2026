from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from packages.models import InstalledStoryPackage, StoryPackageManifest


class StoryPackageError(RuntimeError):
    pass


def load_manifest(manifest_path: Path) -> InstalledStoryPackage:
    try:
        raw: Any = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise StoryPackageError(f"Não foi possível ler {manifest_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise StoryPackageError(f"YAML inválido em {manifest_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise StoryPackageError(f"O manifesto {manifest_path} deve conter um objeto YAML.")

    try:
        manifest = StoryPackageManifest.model_validate(raw)
    except ValidationError as exc:
        raise StoryPackageError(f"Manifesto inválido em {manifest_path}: {exc}") from exc

    root = manifest_path.parent.resolve()
    entrypoint = (root / manifest.entrypoint).resolve()
    if root not in entrypoint.parents:
        raise StoryPackageError("O entrypoint não pode sair da pasta do pacote.")
    if not entrypoint.is_file():
        raise StoryPackageError(f"Entrypoint inexistente: {entrypoint}")

    return InstalledStoryPackage(
        root=root,
        manifest_path=manifest_path.resolve(),
        manifest=manifest,
    )


def discover_packages(root: Path) -> tuple[list[InstalledStoryPackage], list[str]]:
    packages: list[InstalledStoryPackage] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    if not root.exists():
        return packages, errors

    for manifest_path in sorted(root.glob("*/manifest.yaml")):
        try:
            package = load_manifest(manifest_path)
            package_id = package.manifest.package_id
            if package_id in seen_ids:
                raise StoryPackageError(f"package_id duplicado: {package_id}")
            seen_ids.add(package_id)
            packages.append(package)
        except StoryPackageError as exc:
            errors.append(str(exc))

    return packages, errors
