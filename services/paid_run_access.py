from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Literal

from narrative_v2.models import StoryRun
from persistence.models import utc_now_iso
from persistence.v2_factory import build_v2_narrative_repositories

PaidAccessState = Literal["locked", "available", "active"]
ACCESS_CACHE_TTL_SECONDS = 15.0


@dataclass(frozen=True, slots=True)
class PaidRunAccess:
    state: PaidAccessState
    run: StoryRun | None = None

    @property
    def allowed(self) -> bool:
        return self.state in {"available", "active"}


_repository_cache: dict[tuple[str, str, str, int], Any] = {}
_access_cache: dict[tuple[str, str, str, str, int], tuple[float, PaidRunAccess]] = {}


def _configuration_key(secrets: Any) -> tuple[str, str, str, int]:
    service_account = secrets.get("gcp_service_account") or {}
    client_email = ""
    if hasattr(service_account, "get"):
        client_email = str(service_account.get("client_email", "") or "").strip()
    return (
        str(secrets.get("ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID", "") or "").strip(),
        str(secrets.get("ROLEPLAY_RUNTIME_SPREADSHEET_ID", "") or "").strip(),
        client_email,
        id(build_v2_narrative_repositories),
    )


def _repositories(secrets: Any) -> Any:
    key = _configuration_key(secrets)
    cached = _repository_cache.get(key)
    if cached is None:
        cached = build_v2_narrative_repositories(secrets)
        _repository_cache[key] = cached
    return cached


def clear_paid_access_cache(*, user_id: str = "", package_id: str = "") -> None:
    for key in list(_access_cache):
        _accounts_id, _runtime_id, cached_user_id, cached_package_id, _factory_id = key
        if user_id and cached_user_id != user_id:
            continue
        if package_id and cached_package_id != package_id:
            continue
        _access_cache.pop(key, None)


def get_paid_run_access(*, secrets: Any, user_id: str, package_id: str) -> PaidRunAccess:
    configuration = _configuration_key(secrets)
    cache_key = (
        configuration[0],
        configuration[1],
        user_id,
        package_id,
        configuration[3],
    )
    now = monotonic()
    cached = _access_cache.get(cache_key)
    if cached is not None and now < cached[0]:
        return cached[1]

    repositories = _repositories(secrets)
    active = repositories.runs.get_active_run(user_id=user_id, package_id=package_id)
    if active is not None:
        result = PaidRunAccess(state="active", run=active)
    else:
        credit = repositories.credits.get_available_credit(
            user_id=user_id,
            package_id=package_id,
        )
        result = PaidRunAccess(state="available") if credit is not None else PaidRunAccess(state="locked")

    _access_cache[cache_key] = (now + ACCESS_CACHE_TTL_SECONDS, result)
    return result


def finish_active_run(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
    status: Literal["completed", "terminated"],
    ending_code: str,
) -> StoryRun | None:
    repositories = _repositories(secrets)
    run = repositories.runs.get_active_run(user_id=user_id, package_id=package_id)
    if run is None:
        clear_paid_access_cache(user_id=user_id, package_id=package_id)
        return None
    expected_version = run.state_version
    now = utc_now_iso()
    run.status = status
    run.ending_code = ending_code
    run.ended_at = now
    run.updated_at = now
    updated = repositories.runs.update_run(run=run, expected_version=expected_version)
    clear_paid_access_cache(user_id=user_id, package_id=package_id)
    return updated
