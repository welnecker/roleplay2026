from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from narrative_v2.models import StoryRun
from packages.loader import discover_packages
from persistence.v2_factory import build_v2_narrative_repositories


@dataclass(frozen=True, slots=True)
class V2StoryStart:
    script_version: str
    first_block_id: str
    first_beat_id: str


def load_v2_story_start(*, package_id: str, installed_stories_root: Path) -> V2StoryStart | None:
    packages, _errors = discover_packages(installed_stories_root)
    package = next(
        (item for item in packages if item.manifest.package_id == package_id),
        None,
    )
    if package is None:
        return None

    blocks_path = package.root / "blocks.yaml"
    if not blocks_path.is_file():
        return None

    raw = yaml.safe_load(blocks_path.read_text(encoding="utf-8")) or {}
    blocks = raw.get("blocks") if isinstance(raw, dict) else None
    if not isinstance(blocks, list) or not blocks:
        raise ValueError(f"{package_id}: blocks.yaml não contém blocos.")

    ordered = sorted(
        (item for item in blocks if isinstance(item, dict)),
        key=lambda item: int(item.get("order", 0) or 0),
    )
    if not ordered:
        raise ValueError(f"{package_id}: nenhum bloco válido foi encontrado.")

    first = ordered[0]
    first_block_id = str(first.get("block_id", "") or "").strip()
    first_beat_id = str(first.get("entry_beat_id", "") or "").strip()
    if not first_block_id or not first_beat_id:
        raise ValueError(f"{package_id}: bloco inicial incompleto.")

    return V2StoryStart(
        script_version=str(package.manifest.version),
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
    """Inicia uma run apenas quando há crédito disponível.

    A função é idempotente: uma run ativa existente é reutilizada. O crédito só
    é consumido quando a run criada pertence ao mesmo crédito selecionado.
    """

    start = load_v2_story_start(
        package_id=package_id,
        installed_stories_root=installed_stories_root,
    )
    if start is None:
        return None

    repositories = build_v2_narrative_repositories(secrets)
    active = repositories.runs.get_active_run(
        user_id=user_id,
        package_id=package_id,
    )
    if active is not None:
        return active

    credit = repositories.credits.get_available_credit(
        user_id=user_id,
        package_id=package_id,
    )
    if credit is None:
        return None

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
