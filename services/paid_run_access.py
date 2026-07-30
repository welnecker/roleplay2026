from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from narrative_v2.models import StoryRun
from persistence.v2_factory import build_v2_narrative_repositories

PaidAccessState = Literal["locked", "available", "active"]


@dataclass(frozen=True, slots=True)
class PaidRunAccess:
    state: PaidAccessState
    run: StoryRun | None = None

    @property
    def allowed(self) -> bool:
        return self.state in {"available", "active"}


def get_paid_run_access(*, secrets: Any, user_id: str, package_id: str) -> PaidRunAccess:
    repositories = build_v2_narrative_repositories(secrets)
    active = repositories.runs.get_active_run(user_id=user_id, package_id=package_id)
    if active is not None:
        return PaidRunAccess(state="active", run=active)
    credit = repositories.credits.get_available_credit(user_id=user_id, package_id=package_id)
    if credit is not None:
        return PaidRunAccess(state="available")
    return PaidRunAccess(state="locked")


def finish_active_run(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
    status: Literal["completed", "terminated"],
    ending_code: str,
) -> StoryRun | None:
    repositories = build_v2_narrative_repositories(secrets)
    run = repositories.runs.get_active_run(user_id=user_id, package_id=package_id)
    if run is None:
        return None
    expected_version = run.state_version
    run.status = status
    run.ending_code = ending_code
    return repositories.runs.update_run(run=run, expected_version=expected_version)
