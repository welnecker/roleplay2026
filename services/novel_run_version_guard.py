from __future__ import annotations

from typing import Any, Iterable

import streamlit as st

from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository
from roleplay.models import StoryState
from services import editorial_content, runtime_persistence
from services.editorial_compiler import compile_editorial_document
from services.editorial_package_loader import load_editorial_document
from services.editorial_progression import prepare_editorial_script
from services.editorial_runtime import EditorialScript
from services.spreadsheet_story_compiler import compile_spreadsheet_story


_installed = False
_original_load_editorial_package = None
_original_open_persistent_runtime = None


def _user_id_from_session() -> str:
    user = st.session_state.get("authenticated_user")
    return str(getattr(user, "user_id", "") or "").strip()


def _rows_for_version(
    repository: Any,
    *,
    package_id: str,
    script_version: str,
) -> list[dict[str, Any]]:
    """Seleciona somente a versão autoral vinculada à run em andamento."""

    rows: list[dict[str, Any]] = []
    for raw in repository._records("ROTEIROS"):
        row = dict(raw)
        if str(row.get("package_id", "") or "").strip() != package_id:
            continue
        if str(row.get("script_version", "") or "").strip() != script_version:
            continue
        if str(row.get("status", "active") or "active").strip().casefold() != "active":
            continue
        rows.append(row)
    rows.sort(
        key=lambda row: (
            int(row.get("order", 0) or 0),
            str(row.get("line_id", "") or ""),
        )
    )
    return rows


def _load_editorial_package_versioned(
    secrets: Any,
    package: Any,
) -> EditorialScript:
    """Mantém runs ativas na versão em que começaram; novas runs usam a versão atual."""

    assert _original_load_editorial_package is not None
    user_id = _user_id_from_session()
    if not user_id:
        return _original_load_editorial_package(secrets, package)

    script_repository = editorial_content.build_runtime_script_repository(secrets)
    runtime_repository = GoogleSheetsV2RuntimeRepository(script_repository.spreadsheet)
    active_run = runtime_repository.get_active_run(
        user_id=user_id,
        package_id=package.manifest.package_id,
    )
    if active_run is None:
        return _original_load_editorial_package(secrets, package)

    run_version = str(active_run.script_version or "").strip()
    if not run_version:
        raise RuntimeError(
            f"Run ativa sem script_version para {package.manifest.package_id}."
        )

    rows = _rows_for_version(
        script_repository,
        package_id=package.manifest.package_id,
        script_version=run_version,
    )
    if not rows:
        raise RuntimeError(
            "A versão do roteiro vinculada à execução em andamento não está mais disponível: "
            f"package_id={package.manifest.package_id}, script_version={run_version}."
        )

    base_document = load_editorial_document(package)
    document = compile_spreadsheet_story(
        base_document,
        rows,
        script_version=run_version,
    )
    return prepare_editorial_script(
        EditorialScript(compile_editorial_document(document))
    )


def _open_persistent_runtime_without_completed_reactivation(
    repository: Any,
    *,
    user: Any,
    package_id: str,
    package_version: str,
    restart: bool = False,
    instance_id: str | None = None,
) -> tuple[Any, StoryState, list[dict[str, object]]]:
    """Retoma somente run ativa; conclusão antiga nunca vira uma nova compra."""

    assert _original_open_persistent_runtime is not None
    if restart:
        return _original_open_persistent_runtime(
            repository,
            user=user,
            package_id=package_id,
            package_version=package_version,
            restart=True,
            instance_id=instance_id,
        )

    active_run = repository.get_active_run(
        user_id=user.user_id,
        package_id=package_id,
    )
    if active_run is not None:
        if str(active_run.script_version or "").strip() != str(package_version or "").strip():
            raise RuntimeError(
                "A execução ativa foi aberta com uma versão diferente da carregada pelo player: "
                f"run={active_run.script_version}, player={package_version}."
            )
        return _original_open_persistent_runtime(
            repository,
            user=user,
            package_id=package_id,
            package_version=package_version,
            restart=False,
            instance_id=instance_id,
        )

    # O código histórico tentava reativar runs concluídas quando o roteiro crescia.
    # Isso mistura uma compra encerrada com o roteiro atual. Sem run ativa, abrimos
    # um contexto vazio; a primeira mensagem consumirá um crédito novo e criará
    # uma run com a versão editorial vigente.
    return _original_open_persistent_runtime(
        repository,
        user=user,
        package_id=package_id,
        package_version=package_version,
        restart=True,
        instance_id=instance_id,
    )


def install() -> None:
    global _installed
    global _original_load_editorial_package
    global _original_open_persistent_runtime
    if _installed:
        return

    _original_load_editorial_package = editorial_content.load_editorial_package
    _original_open_persistent_runtime = runtime_persistence.open_persistent_runtime
    editorial_content.load_editorial_package = _load_editorial_package_versioned
    runtime_persistence.open_persistent_runtime = (
        _open_persistent_runtime_without_completed_reactivation
    )
    _installed = True


__all__ = ["install"]
