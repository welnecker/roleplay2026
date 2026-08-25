from __future__ import annotations

import shutil
from pathlib import Path


ARCHIVE_DIR_NAME = "_atribuidas"


def _available_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def is_archived_reference(value: str | Path) -> bool:
    path = Path(value)
    return path.parent.name.casefold() == ARCHIVE_DIR_NAME.casefold()


def inferred_original_path(value: str | Path) -> Path | None:
    path = Path(value)
    if not is_archived_reference(path):
        return None
    return path.parent.parent / path.name


def archive_reference(value: str | Path) -> tuple[Path, Path]:
    """Move uma referência disponível para a subpasta de imagens atribuídas.

    Retorna ``(destino_atribuido, origem_original)``. Nunca sobrescreve arquivos.
    """

    source = Path(value)
    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Imagem de referência não encontrada: {source}")

    inferred = inferred_original_path(source)
    if inferred is not None:
        return source, inferred

    archive_dir = source.parent / ARCHIVE_DIR_NAME
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = _available_path(archive_dir / source.name)
    shutil.move(str(source), str(destination))
    return destination, source


def restore_reference(
    archived_value: str | Path,
    original_value: str | Path | None = None,
) -> Path:
    """Devolve uma imagem atribuída à galeria de referências disponíveis.

    Se o nome original já existir, cria um nome seguro em vez de sobrescrever.
    """

    archived = Path(archived_value)
    if not archived.exists() or not archived.is_file():
        raise FileNotFoundError(f"Imagem atribuída não encontrada: {archived}")

    if original_value:
        requested = Path(original_value)
    else:
        inferred = inferred_original_path(archived)
        if inferred is None:
            return archived
        requested = inferred

    if archived == requested:
        return archived

    requested.parent.mkdir(parents=True, exist_ok=True)
    destination = _available_path(requested)
    shutil.move(str(archived), str(destination))
    return destination


__all__ = [
    "ARCHIVE_DIR_NAME",
    "archive_reference",
    "inferred_original_path",
    "is_archived_reference",
    "restore_reference",
]
