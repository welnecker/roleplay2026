from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from narrative_v2.models import RunCredit
from persistence.postgres_accounts import PostgresAccountRepository
from persistence.postgres_database import PostgresDatabase
from persistence.postgres_narrative import PostgresNarrativeRepositories
from persistence.postgres_runtime import PostgresV2RuntimeRepository


pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL não configurada",
)


@pytest.fixture()
def database() -> PostgresDatabase:
    db = PostgresDatabase(os.environ["TEST_DATABASE_URL"], min_size=1, max_size=8)
    db.ensure_schema()
    yield db
    db.close()


def test_concurrent_paid_run_consumes_one_credit(database: PostgresDatabase) -> None:
    accounts = PostgresAccountRepository(database)
    repositories = PostgresNarrativeRepositories(database)
    suffix = uuid4().hex
    user = accounts.register(
        email=f"load-{suffix}@example.test",
        password="senha-segura-123",
        display_name="Load Test",
    )
    credit = repositories.credits.create_credit(
        user_id=user.user_id,
        package_id="roleplay2026.integration",
        payment_id=f"payment-{suffix}",
    )

    def start():
        return repositories.start_paid_run(
            user_id=user.user_id,
            package_id="roleplay2026.integration",
            script_version="test",
            first_block_id="block-1",
            first_beat_id="beat-1",
        )

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _index: start(), range(5)))

    run_ids = {item.run_id for item in results if item is not None}
    assert len(run_ids) == 1
    consumed = repositories.credits.consume_credit(
        credit_id=credit.credit_id,
        run_id=next(iter(run_ids)),
    )
    assert consumed.status == "consumed"


def test_session_and_interaction_are_idempotent(database: PostgresDatabase) -> None:
    accounts = PostgresAccountRepository(database)
    repositories = PostgresNarrativeRepositories(database)
    suffix = uuid4().hex
    user = accounts.register(
        email=f"session-{suffix}@example.test",
        password="senha-segura-123",
        display_name="Session Test",
    )
    free = RunCredit(
        credit_id=f"free-{suffix}", user_id=user.user_id,
        package_id="roleplay2026.integration", payment_id="free",
        status="available",
    )
    run = repositories.runs.create_run(
        credit=free, script_version="test",
        first_block_id="block-1", first_beat_id="beat-1",
    )
    runtime = PostgresV2RuntimeRepository(database)
    session_a = runtime.create_session(
        run_id=run.run_id, user_id=user.user_id,
        package_id=run.package_id, instance_id="same-instance",
    )
    session_b = runtime.create_session(
        run_id=run.run_id, user_id=user.user_id,
        package_id=run.package_id, instance_id="same-instance",
    )
    assert session_a.session_id == session_b.session_id

    values = dict(
        run_id=run.run_id, session_id=session_a.session_id,
        user_id=user.user_id, package_id=run.package_id,
        role="assistant", content="[DESCRIÇÃO] Teste.",
        sequence=1, block_id="block-1", beat_id="beat-1",
    )
    runtime.append_interaction(**values)
    runtime.append_interaction(**values)
    assert len(runtime.list_interactions(run_id=run.run_id)) == 1
