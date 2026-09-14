from __future__ import annotations

import json
from typing import Any

from narrative_v2.models import StoryRun
from narrative_v2.repository import RuntimeConflictError
from persistence.models import new_id
from persistence.postgres_database import PostgresDatabase
from persistence.postgres_narrative import (
    PostgresNarrativeInteractionRepository,
    PostgresStoryRunRepository,
    _run,
    _RUN_COLUMNS,
)
from persistence.runtime_v2 import MAX_RECOVERED_INTERACTIONS, RuntimeSession


class PostgresV2RuntimeRepository:
    """Runtime operacional concorrente; ROTEIROS permanece editorial no Sheets."""

    contract_version = 5

    def __init__(self, database: PostgresDatabase) -> None:
        self.database = database
        self.runs = PostgresStoryRunRepository(database)
        self.interactions = PostgresNarrativeInteractionRepository(database)

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        return self.runs.get_active_run(user_id=user_id, package_id=package_id)

    def get_run(self, *, run_id: str) -> StoryRun | None:
        return self.runs.get_run(run_id=run_id)

    def get_resumable_completed_run(
        self, *, user_id: str, package_id: str
    ) -> StoryRun | None:
        with self.database.pool.connection() as connection:
            rows = connection.execute(
                f"""SELECT {_RUN_COLUMNS}
                    FROM story_runs
                    WHERE user_id = %s AND package_id = %s
                      AND status = 'terminated'
                      AND ending_code = 'mary_lost_interest'
                    ORDER BY updated_at DESC""",
                (user_id, package_id),
            ).fetchall()
            for row in rows:
                run = _run(row)
                messages = connection.execute(
                    """SELECT metadata_json FROM interactions
                       WHERE run_id = %s AND role = 'assistant'
                       ORDER BY sequence DESC LIMIT 2""",
                    (run.run_id,),
                ).fetchall()
                if len(messages) != 2:
                    continue
                newest = dict(messages[0][0] or {})
                previous = dict(messages[1][0] or {})
                if (
                    str(previous.get("pilot_node", "")) == "mensagens_iniciais_001"
                    and str(newest.get("pilot_node", "")) in {"end_lost_interest", "end_pilot"}
                    and str(newest.get("pilot_ending_code", "")) == "mary_lost_interest"
                ):
                    return run
        return None

    def reactivate_run(self, run: StoryRun) -> StoryRun:
        expected_version = run.state_version
        run.status = "active"
        run.ending_code = ""
        run.ended_at = ""
        return self.runs.update_run(run=run, expected_version=expected_version)

    def create_session(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        instance_id: str,
    ) -> RuntimeSession:
        with self.database.pool.connection() as connection:
            with connection.transaction():
                owner = connection.execute(
                    """SELECT 1 FROM story_runs
                       WHERE run_id = %s AND user_id = %s AND package_id = %s""",
                    (run_id, user_id, package_id),
                ).fetchone()
                if owner is None:
                    raise RuntimeConflictError("Run não pertence ao usuário e pacote informados.")
                row = connection.execute(
                    """INSERT INTO runtime_sessions(
                           session_id, run_id, user_id, package_id, instance_id
                       ) VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (run_id, user_id, package_id, instance_id)
                           WHERE status = 'active'
                       DO UPDATE SET last_seen_at = now()
                       RETURNING session_id, run_id, user_id, package_id,
                                 instance_id, status, started_at, last_seen_at, ended_at""",
                    (new_id("sess"), run_id, user_id, package_id, instance_id),
                ).fetchone()
        if row is None:
            raise RuntimeError("Não foi possível criar a sessão.")
        return RuntimeSession(
            session_id=str(row[0]), run_id=str(row[1]), user_id=str(row[2]),
            package_id=str(row[3]), instance_id=str(row[4]), status=str(row[5]),
            started_at=row[6].isoformat(), last_seen_at=row[7].isoformat(),
            ended_at=row[8].isoformat() if row[8] else "",
        )

    def append_interaction(
        self,
        *,
        run_id: str,
        session_id: str,
        user_id: str,
        package_id: str,
        role: str,
        content: str,
        sequence: int,
        block_id: str = "",
        beat_id: str = "",
        speaker_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.interactions.append_interaction(
            run_id=run_id, session_id=session_id, user_id=user_id,
            package_id=package_id, role=role, content=content,
            sequence=sequence, block_id=block_id, beat_id=beat_id,
            speaker_id=speaker_id, metadata=metadata,
        )
        if role == "assistant" and isinstance(metadata, dict):
            self._persist_pending_memories(
                run_id=run_id, source_beat_id=beat_id, metadata=metadata
            )

    def _persist_pending_memories(
        self, *, run_id: str, source_beat_id: str, metadata: dict[str, Any]
    ) -> None:
        editorial = metadata.get("editorial_state")
        legacy = metadata.get("pilot_state")
        state = editorial if isinstance(editorial, dict) else legacy
        if not isinstance(state, dict) or not isinstance(state.get("facts"), dict):
            return
        source = str(metadata.get("editorial_node", "") or source_beat_id).strip()
        raw = str(state["facts"].get("_pending_memory_writes", "") or "")
        for memory_id in (item.strip() for item in raw.split(",")):
            if memory_id:
                self.runs.append_run_memory(
                    run_id=run_id, memory_id=memory_id, source_beat_id=source
                )

    def list_run_memory_ids(self, *, run_id: str) -> list[str]:
        with self.database.pool.connection() as connection:
            rows = connection.execute(
                "SELECT memory_id FROM run_memories WHERE run_id = %s ORDER BY memory_id",
                (run_id,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def list_interactions(
        self, *, run_id: str, limit: int = 100
    ) -> list[dict[str, object]]:
        run = self.get_run(run_id=run_id)
        if run is None:
            raise RuntimeConflictError(f"Run inexistente: {run_id}.")
        safe_limit = max(1, min(int(limit), MAX_RECOVERED_INTERACTIONS))
        result = self.interactions.list_recent_interactions(
            run_id=run_id, limit=safe_limit
        )
        active_ids = self.list_run_memory_ids(run_id=run_id)
        if active_ids:
            for message in reversed(result):
                state = message.get("editorial_state")
                if not isinstance(state, dict):
                    state = message.get("pilot_state")
                if not isinstance(state, dict):
                    continue
                facts = state.setdefault("facts", {})
                if isinstance(facts, dict):
                    facts["_active_memory_ids"] = ",".join(active_ids)
                break
        return result

    def _update_last_assistant_metadata(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        updater: Any,
    ) -> dict[str, Any]:
        with self.database.pool.connection() as connection:
            with connection.transaction():
                row = connection.execute(
                    """SELECT interaction_id, metadata_json, content
                       FROM interactions
                       WHERE run_id = %s AND user_id = %s AND package_id = %s
                         AND role = 'assistant'
                       ORDER BY sequence DESC FOR UPDATE LIMIT 1""",
                    (run_id, user_id, package_id),
                ).fetchone()
                if row is None:
                    raise RuntimeConflictError("A run não possui quadro persistido.")
                metadata = dict(row[1] or {})
                changed = updater(metadata, str(row[2]))
                if changed:
                    connection.execute(
                        "UPDATE interactions SET metadata_json = %s::jsonb WHERE interaction_id = %s",
                        (json.dumps(metadata, ensure_ascii=False), str(row[0])),
                    )
        return metadata

    def persist_frame_reveal(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        frame_id: str,
        revealed_entries: int,
    ) -> int:
        from services.novel_frame_reveal import frame_entry_count, frame_id as content_frame_id

        value = 0
        def update(metadata: dict[str, Any], content: str) -> bool:
            nonlocal value
            if content_frame_id(content) != frame_id:
                raise RuntimeConflictError("Quadro atual não encontrado em INTERACTIONS.")
            value = min(max(0, int(revealed_entries)), frame_entry_count(content))
            value = max(int(metadata.get("flet_revealed_entries", 0) or 0), value)
            metadata["flet_revealed_entries"] = value
            return True
        self._update_last_assistant_metadata(
            run_id=run_id, user_id=user_id, package_id=package_id, updater=update
        )
        return value

    def persist_run_profile(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        profile: dict[str, Any],
    ) -> None:
        def update(metadata: dict[str, Any], _content: str) -> bool:
            if isinstance(metadata.get("immersive_profile"), dict):
                return False
            metadata["immersive_profile"] = dict(profile)
            return True
        self._update_last_assistant_metadata(
            run_id=run_id, user_id=user_id, package_id=package_id, updater=update
        )

    def update_run_progress(
        self, *, run: StoryRun, block_id: str, beat_id: str
    ) -> StoryRun:
        desired_block = block_id or run.current_block_id
        desired_beat = beat_id or run.current_beat_id
        run.current_block_id = desired_block
        run.current_beat_id = desired_beat
        try:
            return self.runs.update_run(run=run, expected_version=run.state_version)
        except RuntimeConflictError:
            current = self.get_run(run_id=run.run_id)
            if current is None:
                raise
            if (
                current.current_block_id == desired_block
                and current.current_beat_id == desired_beat
            ):
                return current
            current.current_block_id = desired_block
            current.current_beat_id = desired_beat
            return self.runs.update_run(
                run=current, expected_version=current.state_version
            )


__all__ = ["PostgresV2RuntimeRepository"]
