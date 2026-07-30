from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from narrative_v2.models import StoryRun
from persistence.v2_factory import build_v2_narrative_repositories
from services.editorial_content import load_editorial_story_start


@dataclass(frozen=True, slots=True)
class V2StoryStart:
    script_version: str
    first_block_id: str
    first_beat_id: str


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

    ``installed_stories_root`` permanece na assinatura por compatibilidade com os
    chamadores existentes, mas não é usado como fonte editorial.
    """

    del installed_stories_root
    start = load_v2_story_start(secrets=secrets, package_id=package_id)
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
