from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from psycopg.errors import UniqueViolation

from narrative_v2.models import RunCredit, StoryRun
from narrative_v2.repository import RuntimeConflictError
from persistence.models import new_id
from persistence.postgres_database import PostgresDatabase


def _iso(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _credit(row: tuple[Any, ...]) -> RunCredit:
    return RunCredit(
        credit_id=str(row[0]),
        user_id=str(row[1]),
        package_id=str(row[2]),
        payment_id=str(row[3]),
        status=str(row[4]),  # type: ignore[arg-type]
        run_id=str(row[5] or ""),
        created_at=_iso(row[6]),
        consumed_at=_iso(row[7]),
    )


def _run(row: tuple[Any, ...]) -> StoryRun:
    memories = row[10] if isinstance(row[10], list) else json.loads(row[10] or "[]")
    return StoryRun(
        run_id=str(row[0]),
        credit_id=str(row[1] or ""),
        user_id=str(row[2]),
        package_id=str(row[3]),
        script_version=str(row[4]),
        current_block_id=str(row[5]),
        current_beat_id=str(row[6]),
        status=str(row[7]),  # type: ignore[arg-type]
        ending_code=str(row[8] or ""),
        state_version=int(row[9]),
        permanent_memory_ids=[str(item) for item in memories],
        started_at=_iso(row[11]),
        ended_at=_iso(row[12]),
        updated_at=_iso(row[13]),
    )


_CREDIT_COLUMNS = """
credit_id, user_id, package_id, payment_id, status, run_id,
created_at, consumed_at
"""
_RUN_COLUMNS = """
run_id, credit_id, user_id, package_id, script_version,
current_block_id, current_beat_id, status, ending_code,
state_version, permanent_memory_ids_json, started_at, ended_at, updated_at
"""


class PostgresStoryCreditRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database

    def create_credit(
        self, *, user_id: str, package_id: str, payment_id: str
    ) -> RunCredit:
        clean_payment = payment_id.strip()
        if not clean_payment:
            raise ValueError("payment_id é obrigatório.")
        credit_id = new_id("credit")
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"""
                INSERT INTO story_credits(
                    credit_id, user_id, package_id, payment_id, status
                )
                VALUES (%s, %s, %s, %s, 'available')
                ON CONFLICT (package_id, payment_id)
                DO UPDATE SET payment_id = EXCLUDED.payment_id
                RETURNING {_CREDIT_COLUMNS}
                """,
                (credit_id, user_id, package_id, clean_payment),
            ).fetchone()
        if row is None:
            raise RuntimeError("Não foi possível criar o crédito.")
        result = _credit(row)
        if result.user_id != user_id:
            raise RuntimeConflictError(
                f"Pagamento {clean_payment} já está associado a outro usuário."
            )
        return result

    def get_available_credit(
        self, *, user_id: str, package_id: str
    ) -> RunCredit | None:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"""
                SELECT {_CREDIT_COLUMNS}
                FROM story_credits
                WHERE user_id = %s
                  AND package_id = %s
                  AND status = 'available'
                ORDER BY created_at
                LIMIT 1
                """,
                (user_id, package_id),
            ).fetchone()
        return _credit(row) if row is not None else None

    def consume_credit(self, *, credit_id: str, run_id: str) -> RunCredit:
        with self.database.pool.connection() as connection:
            with connection.transaction():
                row = connection.execute(
                    f"""
                    SELECT {_CREDIT_COLUMNS}
                    FROM story_credits
                    WHERE credit_id = %s
                    FOR UPDATE
                    """,
                    (credit_id,),
                ).fetchone()
                if row is None:
                    raise KeyError(f"Crédito não encontrado: {credit_id}")
                current = _credit(row)
                if current.status == "consumed" and current.run_id == run_id:
                    return current
                if current.status != "available":
                    raise RuntimeConflictError(
                        f"Crédito {credit_id} não está disponível: {current.status}."
                    )
                updated = connection.execute(
                    f"""
                    UPDATE story_credits
                    SET status = 'consumed', run_id = %s, consumed_at = now()
                    WHERE credit_id = %s
                    RETURNING {_CREDIT_COLUMNS}
                    """,
                    (run_id, credit_id),
                ).fetchone()
        if updated is None:
            raise RuntimeError("Não foi possível consumir o crédito.")
        return _credit(updated)


class PostgresStoryRunRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database

    def create_run(
        self,
        *,
        credit: RunCredit,
        script_version: str,
        first_block_id: str,
        first_beat_id: str,
    ) -> StoryRun:
        run_id = new_id("run")
        try:
            with self.database.pool.connection() as connection:
                with connection.transaction():
                    existing = connection.execute(
                        f"""
                        SELECT {_RUN_COLUMNS}
                        FROM story_runs
                        WHERE user_id = %s
                          AND package_id = %s
                          AND status = 'active'
                        FOR UPDATE
                        LIMIT 1
                        """,
                        (credit.user_id, credit.package_id),
                    ).fetchone()
                    if existing is not None:
                        return _run(existing)
                    if credit.status not in {"available", "consumed"}:
                        raise RuntimeConflictError(
                            f"Crédito {credit.credit_id} não pode iniciar uma run: "
                            f"{credit.status}."
                        )
                    created = connection.execute(
                        f"""
                        INSERT INTO story_runs(
                            run_id, credit_id, user_id, package_id,
                            script_version, current_block_id, current_beat_id
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING {_RUN_COLUMNS}
                        """,
                        (
                            run_id,
                            credit.credit_id,
                            credit.user_id,
                            credit.package_id,
                            script_version,
                            first_block_id,
                            first_beat_id,
                        ),
                    ).fetchone()
        except UniqueViolation:
            existing_run = self.get_active_run(
                user_id=credit.user_id,
                package_id=credit.package_id,
            )
            if existing_run is not None:
                return existing_run
            raise
        if created is None:
            raise RuntimeError("Não foi possível criar a execução.")
        return _run(created)

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"""
                SELECT {_RUN_COLUMNS}
                FROM story_runs
                WHERE user_id = %s
                  AND package_id = %s
                  AND status = 'active'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id, package_id),
            ).fetchone()
        return _run(row) if row is not None else None

    def get_run(self, *, run_id: str) -> StoryRun | None:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"SELECT {_RUN_COLUMNS} FROM story_runs WHERE run_id = %s",
                (run_id,),
            ).fetchone()
        return _run(row) if row is not None else None

    def update_run(self, *, run: StoryRun, expected_version: int) -> StoryRun:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                f"""
                UPDATE story_runs
                SET current_block_id = %s,
                    current_beat_id = %s,
                    status = %s,
                    ending_code = %s,
                    permanent_memory_ids_json = %s::jsonb,
                    ended_at = %s,
                    updated_at = now(),
                    state_version = state_version + 1
                WHERE run_id = %s AND state_version = %s
                RETURNING {_RUN_COLUMNS}
                """,
                (
                    run.current_block_id,
                    run.current_beat_id,
                    run.status,
                    run.ending_code,
                    json.dumps(run.permanent_memory_ids),
                    run.ended_at or None,
                    run.run_id,
                    expected_version,
                ),
            ).fetchone()
        if row is None:
            current = self.get_run(run_id=run.run_id)
            if current is None:
                raise KeyError(f"Run não encontrada: {run.run_id}")
            raise RuntimeConflictError(
                f"Versão concorrente na run {run.run_id}: "
                f"esperada={expected_version}, atual={current.state_version}."
            )
        return _run(row)

    def append_run_memory(
        self, *, run_id: str, memory_id: str, source_beat_id: str
    ) -> None:
        with self.database.pool.connection() as connection:
            connection.execute(
                """
                INSERT INTO run_memories(
                    run_memory_id, run_id, memory_id, source_beat_id
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id, memory_id) DO NOTHING
                """,
                (new_id("rmem"), run_id, memory_id, source_beat_id),
            )


class PostgresNarrativeInteractionRepository:
    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database

    def append_interaction(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        sequence: int,
        role: str,
        content: str,
        block_id: str,
        beat_id: str,
        speaker_id: str,
        user_intent: str = "",
        beat_consumed: bool = False,
        input_tokens: int = 0,
        output_tokens: int = 0,
        session_id: str = "",
        model: str = "",
        latency_ms: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.database.pool.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO interactions(
                    interaction_id, session_id, run_id, user_id, package_id,
                    sequence, role, speaker_id, content, block_id, beat_id,
                    user_intent, beat_consumed, model, input_tokens,
                    output_tokens, latency_ms, metadata_json
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
                )
                ON CONFLICT (run_id, sequence, role)
                DO UPDATE SET content = interactions.content
                RETURNING content
                """,
                (
                    new_id("int"),
                    session_id,
                    run_id,
                    user_id,
                    package_id,
                    sequence,
                    role,
                    speaker_id,
                    content,
                    block_id,
                    beat_id,
                    user_intent,
                    beat_consumed,
                    model,
                    input_tokens,
                    output_tokens,
                    latency_ms,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            ).fetchone()
        if row is None or str(row[0]) != content:
            raise RuntimeConflictError(
                f"Interação concorrente incompatível na run {run_id}, "
                f"sequência={sequence}, role={role}."
            )

    def list_recent_interactions(
        self, *, run_id: str, limit: int = 6
    ) -> list[dict[str, object]]:
        safe_limit = max(1, min(int(limit), 500))
        with self.database.pool.connection() as connection:
            rows = connection.execute(
                """
                SELECT role, content, sequence, block_id, beat_id, metadata_json
                FROM interactions
                WHERE run_id = %s
                ORDER BY sequence DESC
                LIMIT %s
                """,
                (run_id, safe_limit),
            ).fetchall()
        result: list[dict[str, object]] = []
        for row in reversed(rows):
            metadata = dict(row[5] or {})
            result.append(
                {
                    "role": str(row[0]),
                    "content": str(row[1]),
                    "sequence": int(row[2]),
                    "block_id": str(row[3] or ""),
                    "beat_id": str(row[4] or ""),
                    **metadata,
                }
            )
        return result


class PostgresNarrativeRepositories:
    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database
        self.credits = PostgresStoryCreditRepository(database)
        self.runs = PostgresStoryRunRepository(database)
        self.interactions = PostgresNarrativeInteractionRepository(database)

    def start_paid_run(
        self,
        *,
        user_id: str,
        package_id: str,
        script_version: str,
        first_block_id: str,
        first_beat_id: str,
    ) -> StoryRun | None:
        """Reserva crédito, cria run e consome crédito em uma transação."""

        with self.database.pool.connection() as connection:
            with connection.transaction():
                existing = connection.execute(
                    f"""
                    SELECT {_RUN_COLUMNS}
                    FROM story_runs
                    WHERE user_id = %s
                      AND package_id = %s
                      AND status = 'active'
                    FOR UPDATE
                    LIMIT 1
                    """,
                    (user_id, package_id),
                ).fetchone()
                if existing is not None:
                    return _run(existing)
                credit_row = connection.execute(
                    f"""
                    SELECT {_CREDIT_COLUMNS}
                    FROM story_credits
                    WHERE user_id = %s
                      AND package_id = %s
                      AND status = 'available'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """,
                    (user_id, package_id),
                ).fetchone()
                if credit_row is None:
                    return None
                credit = _credit(credit_row)
                run_id = new_id("run")
                created = connection.execute(
                    f"""
                    INSERT INTO story_runs(
                        run_id, credit_id, user_id, package_id,
                        script_version, current_block_id, current_beat_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING {_RUN_COLUMNS}
                    """,
                    (
                        run_id,
                        credit.credit_id,
                        user_id,
                        package_id,
                        script_version,
                        first_block_id,
                        first_beat_id,
                    ),
                ).fetchone()
                connection.execute(
                    """
                    UPDATE story_credits
                    SET status = 'consumed', run_id = %s, consumed_at = now()
                    WHERE credit_id = %s AND status = 'available'
                    """,
                    (run_id, credit.credit_id),
                )
        if created is None:
            raise RuntimeError("Não foi possível iniciar a execução paga.")
        return _run(created)


__all__ = [
    "PostgresNarrativeInteractionRepository",
    "PostgresNarrativeRepositories",
    "PostgresStoryCreditRepository",
    "PostgresStoryRunRepository",
]
