from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from packages.loader import discover_packages
from packages.models import InstalledStoryPackage
from persistence.editorial import GoogleSheetsEditorialRepository
from persistence.editorial_publisher import publish_editorial_document
from persistence.spreadsheet_config import read_spreadsheet_ids
from services import editorial_runtime_impl as runtime_impl
from services.editorial_compiler import compile_editorial_document
from services.editorial_package_loader import (
    compile_editorial_package,
    editorial_story_start,
    load_editorial_document,
)
from services.editorial_progression import (
    clean_editorial_progression_response,
    decide_editorial_progression_turn,
    prepare_editorial_script,
)
from services.editorial_runtime import EditorialScript
from services.spreadsheet_story_compiler import compile_spreadsheet_story


INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent.parent / "installed_stories"
LEGACY_EDITORIAL_PACKAGE_ID = "roleplay2026.casada_frustrada"
_EDITORIAL_REPOSITORY: GoogleSheetsEditorialRepository | None = None
_SCRIPT_REPOSITORY: GoogleSheetsEditorialRepository | None = None
_PUBLISHED_PACKAGES: set[str] = set()
_FREE_TEXT_KEYS = {
    "introduction",
    "title",
    "required_movement",
    "canonical_line",
    "dramatic_direction",
    "text",
    "summary",
}
_FREE_TEXT_PATTERN = re.compile(
    r"^(?P<indent>\s*)(?P<key>" + "|".join(sorted(_FREE_TEXT_KEYS)) + r"):\s*(?P<value>.*)$"
)

# Compatibilidade interna enquanto a implementação histórica ainda delega sua
# decisão avançada ao módulo de progressão editorial.
runtime_impl.decide_turn = decide_editorial_progression_turn
runtime_impl.clean_model_response = clean_editorial_progression_response


def _protect_editorial_plain_scalars(text: str) -> str:
    protected: list[str] = []
    for line in text.splitlines():
        match = _FREE_TEXT_PATTERN.match(line)
        if match is None:
            protected.append(line)
            continue
        value = match.group("value")
        stripped = value.lstrip()
        if not stripped or stripped.startswith(("'", '"', "|", ">", "[", "{")):
            protected.append(line)
            continue
        protected.append(
            f'{match.group("indent")}{match.group("key")}: '
            f'{json.dumps(value, ensure_ascii=False)}'
        )
    return "\n".join(protected) + ("\n" if text.endswith("\n") else "")


def load_editorial_yaml_text(text: str) -> dict[str, Any]:
    """Compatibilidade pública para testes e ferramentas editoriais."""

    raw = yaml.safe_load(_protect_editorial_plain_scalars(text))
    if not isinstance(raw, dict):
        raise ValueError("Documento editorial YAML inválido")
    return raw


def _all_packages() -> tuple[InstalledStoryPackage, ...]:
    packages, errors = discover_packages(INSTALLED_STORIES_ROOT)
    if errors:
        raise ValueError("; ".join(errors))
    return tuple(packages)


def editorial_packages() -> tuple[InstalledStoryPackage, ...]:
    return tuple(
        package
        for package in _all_packages()
        if package.manifest.runtime.kind == "editorial"
    )


def find_editorial_package(package_id: str) -> InstalledStoryPackage | None:
    clean = str(package_id or "").strip().lower()
    return next(
        (
            package
            for package in editorial_packages()
            if package.manifest.package_id == clean
        ),
        None,
    )


def require_editorial_package(package_id: str) -> InstalledStoryPackage:
    """Resolve uma história sem depender da quantidade ou da ordem dos pacotes."""

    clean = str(package_id or "").strip().lower()
    if not clean:
        raise ValueError("package_id da história é obrigatório")
    package = find_editorial_package(clean)
    if package is None:
        available = [item.manifest.package_id for item in editorial_packages()]
        raise ValueError(
            f"História editorial não encontrada: {clean!r}. Disponíveis: {available}"
        )
    return package


def _default_editorial_package() -> InstalledStoryPackage:
    """Compatibilidade determinística para chamadas antigas específicas da Mary."""

    return require_editorial_package(LEGACY_EDITORIAL_PACKAGE_ID)


def load_source_document(
    package: InstalledStoryPackage | str | None = None,
) -> dict[str, Any]:
    selected = (
        require_editorial_package(package)
        if isinstance(package, str)
        else package or _default_editorial_package()
    )
    return load_editorial_document(selected)


def build_editorial_repository(secrets: Any) -> GoogleSheetsEditorialRepository:
    global _EDITORIAL_REPOSITORY
    if _EDITORIAL_REPOSITORY is not None:
        return _EDITORIAL_REPOSITORY
    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("[gcp_service_account] não está configurado")
    ids = read_spreadsheet_ids(secrets)
    _EDITORIAL_REPOSITORY = GoogleSheetsEditorialRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=ids.editorial,
    )
    return _EDITORIAL_REPOSITORY


def build_runtime_script_repository(
    secrets: Any,
) -> GoogleSheetsEditorialRepository:
    """Abre somente ROTEIROS na planilha ROLEPLAY_RUNTIME."""

    global _SCRIPT_REPOSITORY
    if _SCRIPT_REPOSITORY is not None:
        return _SCRIPT_REPOSITORY
    credentials = secrets.get("gcp_service_account")
    if not credentials:
        raise ValueError("[gcp_service_account] não está configurado")
    ids = read_spreadsheet_ids(secrets)
    _SCRIPT_REPOSITORY = GoogleSheetsEditorialRepository.from_service_account(
        credentials=dict(credentials),
        spreadsheet_id=ids.runtime,
    )
    return _SCRIPT_REPOSITORY


def ensure_editorial_package(
    secrets: Any,
    package: InstalledStoryPackage,
) -> GoogleSheetsEditorialRepository:
    repository = build_editorial_repository(secrets)
    package_id = package.manifest.package_id
    if package_id in _PUBLISHED_PACKAGES:
        return repository
    repository.ensure_schema()
    publish_editorial_document(repository, load_editorial_document(package))
    _PUBLISHED_PACKAGES.add(package_id)
    return repository


def ensure_editorial_pilot(secrets: Any) -> GoogleSheetsEditorialRepository:
    """Fachada temporária para chamadas antigas durante a migração."""

    return ensure_editorial_package(secrets, _default_editorial_package())


def load_effective_editorial_document(
    secrets: Any,
    package: InstalledStoryPackage,
) -> dict[str, Any]:
    """Prefere ROTEIROS e preserva o YAML como fallback de migração."""

    ensure_editorial_package(secrets, package)
    script_repository = build_runtime_script_repository(secrets)
    base_document = load_editorial_document(package)
    script_version, rows = script_repository.load_active_story_lines(
        package.manifest.package_id
    )
    if not rows:
        return base_document
    return compile_spreadsheet_story(
        base_document,
        rows,
        script_version=script_version,
    )


def load_editorial_package(
    secrets: Any,
    package: InstalledStoryPackage,
) -> EditorialScript:
    document = load_effective_editorial_document(secrets, package)
    return prepare_editorial_script(
        EditorialScript(compile_editorial_document(document))
    )


def load_editorial_pilot(secrets: Any) -> EditorialScript:
    """Fachada temporária; novos fluxos devem passar o pacote explicitamente."""

    package = _default_editorial_package()
    return load_editorial_package(secrets, package)


def load_editorial_story_start(
    secrets: Any,
    package_id: str,
) -> tuple[str, str, str] | None:
    package = find_editorial_package(package_id)
    if package is None:
        return None
    document = load_effective_editorial_document(secrets, package)
    blocks = [item for item in document.get("blocks", []) if isinstance(item, dict)]
    if not blocks:
        return None
    first = min(blocks, key=lambda item: int(item.get("order", 0) or 0))
    return (
        str(document.get("script_version", "")),
        str(first.get("block_id", "")),
        str(first.get("entry_beat_id", "")),
    )
