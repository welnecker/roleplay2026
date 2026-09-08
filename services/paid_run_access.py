from __future__ import annotations

import json
from dataclasses import dataclass
from time import monotonic
from typing import Any, Literal

from narrative_v2.models import StoryRun
from persistence.models import utc_now_iso
from persistence.v2_factory import build_v2_narrative_repositories

PaidAccessState = Literal["locked", "available", "active"]
ACCESS_CACHE_TTL_SECONDS = 60.0


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


def _access_cache_key(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
) -> tuple[str, str, str, str, int]:
    configuration = _configuration_key(secrets)
    return (
        configuration[0],
        configuration[1],
        user_id,
        package_id,
        configuration[3],
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


def prime_paid_access_available(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
    ttl_seconds: float = ACCESS_CACHE_TTL_SECONDS,
) -> PaidRunAccess:
    """Registra o crédito recém-criado sem consultar novamente o Sheets."""

    result = PaidRunAccess(state="available")
    cache_key = _access_cache_key(
        secrets=secrets,
        user_id=user_id,
        package_id=package_id,
    )
    _access_cache[cache_key] = (monotonic() + max(1.0, float(ttl_seconds)), result)
    return result


def _cached_active_run(*, secrets: Any, user_id: str, package_id: str) -> StoryRun | None:
    cached = _access_cache.get(
        _access_cache_key(secrets=secrets, user_id=user_id, package_id=package_id)
    )
    if cached is None:
        return None
    _expires_at, access = cached
    if access.state != "active" or access.run is None:
        return None
    return access.run


def _persisted_end_for_run(repositories: Any, run_id: str) -> tuple[str, str] | None:
    """Reconcilia runs antigas que salvaram o FIM antes de atualizar RUNS."""

    interactions = getattr(repositories, "interactions", None)
    table = getattr(interactions, "table", None)
    records = getattr(table, "records", None)
    if not callable(records):
        return None
    candidates = [
        row
        for row in records()
        if str(row.get("run_id", "") or "").strip() == run_id
        and str(row.get("role", "") or "").strip() == "assistant"
    ]
    candidates.sort(key=lambda row: int(row.get("sequence", 0) or 0), reverse=True)
    for row in candidates:
        try:
            metadata = json.loads(str(row.get("metadata_json", "") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict):
            continue
        story_state = metadata.get("_story_state")
        ended = metadata.get("editorial_end_event") == "END_RUN" or (
            isinstance(story_state, dict) and bool(story_state.get("finished"))
        )
        if not ended:
            return None
        requested = str(
            metadata.get("editorial_run_status")
            or metadata.get("pilot_run_status")
            or "completed"
        )
        status = "terminated" if requested == "terminated" else "completed"
        ending_code = str(
            metadata.get("editorial_ending_code")
            or metadata.get("pilot_ending_code")
            or "normal_completion"
        )
        return status, ending_code
    return None


def get_paid_run_access(*, secrets: Any, user_id: str, package_id: str) -> PaidRunAccess:
    cache_key = _access_cache_key(
        secrets=secrets,
        user_id=user_id,
        package_id=package_id,
    )
    now = monotonic()
    cached = _access_cache.get(cache_key)
    if cached is not None and now < cached[0]:
        return cached[1]

    repositories = _repositories(secrets)
    active = repositories.runs.get_active_run(user_id=user_id, package_id=package_id)
    if active is not None:
        persisted_end = _persisted_end_for_run(repositories, active.run_id)
        if persisted_end is not None:
            finish_active_run(
                secrets=secrets,
                user_id=user_id,
                package_id=package_id,
                status=persisted_end[0],  # type: ignore[arg-type]
                ending_code=persisted_end[1],
            )
            active = None
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


def revoke_available_credits(*, secrets: Any, user_id: str, package_id: str) -> int:
    """Revoga créditos disponíveis residuais ao encerrar explicitamente a história."""

    repositories = _repositories(secrets)
    table = repositories.credits.table
    revoked = 0
    now = utc_now_iso()
    for row_number, row in enumerate(table.records(), start=2):
        if str(row.get("user_id", "")).strip() != user_id:
            continue
        if str(row.get("package_id", "")).strip() != package_id:
            continue
        if str(row.get("status", "")).strip() != "available":
            continue
        updated = dict(row)
        updated["status"] = "revoked"
        updated["revoked_at"] = now
        table.replace(row_number, updated)
        revoked += 1

    clear_paid_access_cache(user_id=user_id, package_id=package_id)
    return revoked


def _is_concurrent_version_error(exc: BaseException) -> bool:
    message = str(exc).casefold()
    return "versão concorrente" in message or "versao concorrente" in message


def finish_active_run(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
    status: Literal["completed", "terminated"],
    ending_code: str,
) -> StoryRun | None:
    """Finaliza a run e refaz uma vez a atualização quando a versão ficou obsoleta.

    As interações finais podem incrementar ``state_version`` imediatamente antes do
    encerramento. Nesse caso, o objeto em cache está correto quanto à identidade da
    run, mas traz uma versão anterior. Recarregar a run ativa e repetir a atualização
    torna o fechamento idempotente sem ocultar outros tipos de erro.
    """

    repositories = _repositories(secrets)

    for attempt in range(2):
        run = repositories.runs.get_active_run(
            user_id=user_id,
            package_id=package_id,
        )
        if run is None:
            clear_paid_access_cache(user_id=user_id, package_id=package_id)
            return None

        expected_version = run.state_version
        now = utc_now_iso()
        run.status = status
        run.ending_code = ending_code
        run.ended_at = now
        run.updated_at = now
        try:
            updated = repositories.runs.update_run(
                run=run,
                expected_version=expected_version,
            )
        except Exception as exc:
            if attempt == 0 and _is_concurrent_version_error(exc):
                clear_paid_access_cache(user_id=user_id, package_id=package_id)
                continue
            raise

        clear_paid_access_cache(user_id=user_id, package_id=package_id)
        return updated

    return None


def terminate_paid_access(
    *,
    secrets: Any,
    user_id: str,
    package_id: str,
    ending_code: str,
) -> StoryRun | None:
    """Encerra a run e bloqueia qualquer crédito residual até um novo pagamento."""

    ended = finish_active_run(
        secrets=secrets,
        user_id=user_id,
        package_id=package_id,
        status="terminated",
        ending_code=ending_code,
    )
    revoke_available_credits(
        secrets=secrets,
        user_id=user_id,
        package_id=package_id,
    )
    clear_paid_access_cache(user_id=user_id, package_id=package_id)
    return ended
