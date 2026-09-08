from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable


DEFAULT_REFERENCE_DIR = Path(r"C:\Users\welne\Downloads\PROJETO\IMAGENS")
REFERENCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def reference_images_from_directory(directory: str | Path) -> list[str]:
    """Lista imagens do diretório sem mover ou alterar arquivos."""

    root = Path(directory)
    if not root.is_dir():
        return []
    return [
        str(path)
        for path in sorted(root.iterdir(), key=lambda item: item.name.casefold())
        if path.is_file() and path.suffix.casefold() in REFERENCE_SUFFIXES
    ]


def reference_directory_from_project(data: dict[str, Any]) -> str:
    """Recupera a pasta salva ou a infere das imagens de um projeto antigo."""

    saved = str(data.get("reference_directory", "") or "").strip()
    if saved:
        return saved

    candidates: list[str] = [
        str(value)
        for value in data.get("reference_files", []) or []
        if str(value or "").strip()
    ]
    candidates.extend(
        str(value)
        for value in dict(data.get("image_sources", {}) or {}).values()
        if str(value or "").strip()
    )
    parents = {str(Path(value).parent) for value in candidates}
    return parents.pop() if len(parents) == 1 else ""


def existing_initial_directory(
    current: str | Path | None,
    *,
    fallbacks: Iterable[str | Path] = (),
) -> str:
    for candidate in (current, *fallbacks, Path.home()):
        if candidate and Path(candidate).is_dir():
            return str(candidate)
    return str(Path.home())


__all__ = [
    "DEFAULT_REFERENCE_DIR",
    "REFERENCE_SUFFIXES",
    "existing_initial_directory",
    "reference_directory_from_project",
    "reference_images_from_directory",
]
