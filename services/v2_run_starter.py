from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from narrative_v2.models import RunCredit, StoryRun
from packages.loader import discover_packages
from persistence.v2_factory import build_v2_narrative_repositories
from services.editorial_content import load_editorial_story_start


@dataclass(frozen=True, slots=True)
class V2StoryStart:
    script_version: str
    first_block_id: str
    first_beat_id: str


def _package_access(*, installed_stories_root: Path, package_id: str) -> str:
    """Resolve o acesso pelo manifesto; pacote ausente permanece protegido como pago."""

    packages, _errors = discover_packages(installed_stories_root)
    for package in packages:
        if package.manifest.package_id == package_id:
            return package.manifest.commerce.access
    return "paid"


def load_v2_story_start(*, secrets: Any, package_id: str) -> V2StoryStart | None:
    values = load_editorial_story_start(secrets, package_id)
    if values is None:
        return None
    script_version, first_block_id, first_beat_id = values
    if not script_version or not first_block_id or not first_beat_id:
        raise ValueError(f"{package_id}: início editorial incompleto em STORIES.")
    return V2StoryStart(
        script_version=script_version,
        first_block_id=first_block_id,
        first_beat_id=first_beat_id,
    )


def start_v2_run_on_first_message(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
    installed_stories_root: Path,
) -> StoryRun | None:
    """Inicia uma run usando exclusivamente a definição publicada no editorial.

    O manifesto do próprio pacote determina se a execução usa acesso gratuito ou
    crédito pago. Assim, novos cards editoriais respeitam ``commerce.access`` sem
    qualquer lista fixa por ``package_id``.

    Na abertura de uma nova execução, o runtime chamador já consultou a run ativa.
    Evitamos repetir aqui a mesma consulta antes de olhar o crédito: quando existe
    crédito disponível, ``create_run`` continua fazendo a confirmação final de run
    ativa imediatamente antes do append. Quando não existe crédito, ainda
    consultamos a run ativa para preservar a retomada/reutilização existente.
    """

    access = _package_access(
        installed_stories_root=installed_stories_root,
        package_id=package_id,
    )
    start = load_v2_story_start(secrets=secrets, package_id=package_id)
    if start is None:
        return None

    repositories = build_v2_narrative_repositories(secrets)
    if access == "free":
        free_access = RunCredit(
            credit_id=f"free:{package_id}:{user_id}",
            user_id=user_id,
            package_id=package_id,
            payment_id="free",
            status="available",
        )
        return repositories.runs.create_run(
            credit=free_access,
            script_version=start.script_version,
            first_block_id=start.first_block_id,
            first_beat_id=start.first_beat_id,
        )

    start_paid_run = getattr(repositories, "start_paid_run", None)
    if callable(start_paid_run):
        return start_paid_run(
            user_id=user_id,
            package_id=package_id,
            script_version=start.script_version,
            first_block_id=start.first_block_id,
            first_beat_id=start.first_beat_id,
        )

    credit = repositories.credits.get_available_credit(
        user_id=user_id,
        package_id=package_id,
    )
    if credit is None:
        return repositories.runs.get_active_run(
            user_id=user_id,
            package_id=package_id,
        )

    run = repositories.runs.create_run(
        credit=credit,
        script_version=start.script_version,
        first_block_id=start.first_block_id,
        first_beat_id=start.first_beat_id,
    )
    if run.credit_id == credit.credit_id:
        repositories.credits.consume_credit(
            credit_id=credit.credit_id,
            run_id=run.run_id,
        )
    return run
