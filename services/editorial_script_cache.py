from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import ModuleType

from packages.models import InstalledStoryPackage


_CACHE_FINGERPRINT_ATTR = "_editorial_package_fingerprint"


def editorial_package_fingerprint(package: InstalledStoryPackage) -> str:
    """Calcula uma impressão digital dos arquivos que formam o roteiro do card."""

    runtime = package.manifest.runtime
    if runtime.kind != "editorial" or runtime.editorial is None:
        raise ValueError(
            f"Pacote {package.manifest.package_id!r} não declara runtime editorial"
        )

    root = package.root.resolve()
    relative_paths = (
        "manifest.yaml",
        runtime.editorial.source,
        *runtime.editorial.extensions,
    )
    digest = sha256()
    for relative_path in relative_paths:
        target = (root / relative_path).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"Arquivo editorial fora do pacote: {relative_path}")
        if not target.is_file():
            raise ValueError(f"Arquivo editorial inexistente: {target}")
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(target.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def refresh_loaded_editorial_script_cache(module: ModuleType) -> bool:
    """Invalida o cache do roteiro quando qualquer arquivo do card mudou.

    O marcador fica anexado ao módulo carregado e sobrevive a ``importlib.reload``.
    Assim, reruns comuns não recompilam o roteiro, mas uma alteração de conteúdo
    declarativo passa a ser percebida sem depender da troca do ``package_id``.
    """

    package = getattr(module, "PACKAGE", None)
    load_script = getattr(module, "load_script", None)
    if not isinstance(package, InstalledStoryPackage) or load_script is None:
        return False

    current = editorial_package_fingerprint(package)
    previous = str(getattr(module, _CACHE_FINGERPRINT_ATTR, "") or "")
    if previous == current:
        return False

    clear = getattr(load_script, "clear", None)
    if callable(clear):
        clear()
    setattr(module, _CACHE_FINGERPRINT_ATTR, current)
    return True


__all__ = [
    "editorial_package_fingerprint",
    "refresh_loaded_editorial_script_cache",
]
