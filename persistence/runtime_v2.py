from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import gspread
from gspread import Spreadsheet

from narrative_v2.models import StoryRun
from persistence.models import new_id, utc_now_iso
from persistence.v2_google_sheets import (
    GoogleSheetsNarrativeInteractionRepository,
    GoogleSheetsStoryRunRepository,
)


MAX_RECOVERED_INTERACTIONS = 500
RUNTIME_REPOSITORY_CONTRACT_VERSION = 4


@dataclass(frozen=True, slots=True)
class RuntimeSession:
    session_id: str
    run_id: str
    user_id: str
    package_id: str
    instance_id: str
    status: str
    started_at: str
    last_seen_at: str
    ended_at: str = ""


class GoogleSheetsV2RuntimeRepository:
    """Runtime operacional gravado exclusivamente em ROLEPLAY_RUNTIME."""

    contract_version = RUNTIME_REPOSITORY_CONTRACT_VERSION

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.spreadsheet = spreadsheet
        self.runs = GoogleSheetsStoryRunRepository(spreadsheet)
        self.interactions = GoogleSheetsNarrativeInteractionRepository(spreadsheet)
        self.sessions = spreadsheet.worksheet("SESSIONS")

    @classmethod
    def from_service_account(
        cls,
        *,
        credentials: dict[str, Any],
        spreadsheet_id: str,
    ) -> "GoogleSheetsV2RuntimeRepository":
        client = gspread.service_account_from_dict(credentials)
        return cls(client.open_by_key(spreadsheet_id))

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        return self.runs.get_active_run(user_id=user_id, package_id=package_id)

    def _was_false_message_ending(self, run: StoryRun) -> bool:
        if run.status != "terminated" or run.ending_code != "mary_lost_interest":
            return False

        rows = [
            row
            for row in self.interactions.table.records()
            if str(row.get("run_id", "")).strip() == run.run_id
            and str(row.get("role", "")).strip() == "assistant"
        ]
        rows.sort(key=lambda row: int(row.get("sequence", 0) or 0))
        nodes: list[str] = []
        ending_codes: list[str] = []
        for row in rows:
            raw_metadata = str(row.get("metadata_json", "") or "")
            try:
                metadata = json.loads(raw_metadata) if raw_metadata else {}
            except json.JSONDecodeError:
                metadata = {}
            if not isinstance(metadata, dict):
                continue
            nodes.append(str(metadata.get("pilot_node", "") or ""))
            ending_codes.append(str(metadata.get("pilot_ending_code", "") or ""))

        return (
            len(nodes) >= 2
            and nodes[-2] == "mensagens_iniciais_001"
            and nodes[-1] in {"end_lost_interest", "end_pilot"}
            and ending_codes[-1] == "mary_lost_interest"
        )

    def get_resumable_completed_run(
        self,
        *,
        user_id: str,
        package_id: str,
    ) -> StoryRun | None:
        """Retorna conclusão normal ou o falso encerramento conhecido da primeira mensagem."""

        candidates: list[StoryRun] = []
        for row in self.runs.runs.records():
            if str(row.get("user_id", "")).strip() != user_id:
                continue
            if str(row.get("package_id", "")).strip() != package_id:
                continue
            run = self.runs._from_row(row)
            normal_completion = (
                run.status == "completed"
                and run.ending_code in {"", "normal_completion", "pilot_complete"}
            )
            if normal_completion or self._was_false_message_ending(run):
                candidates.append(run)

        if not candidates:
            return None
        candidates.sort(key=lambda run: run.updated_at, reverse=True)
        return candidates[0]

    def reactivate_run(self, run: StoryRun) -> StoryRun:
        expected_version = run.state_version
        run.status = "active"
        run.ending_code = ""
        run.ended_at = ""
        run.updated_at = utc_now_iso()
        return self.runs.update_run(run=run, expected_version=expected_version)

    def create_session(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        instance_id: str,
    ) -> RuntimeSession:
        now = utc_now_iso()
        session = RuntimeSession(
            session_id=new_id("sess"),
            run_id=run_id,
            user_id=user_id,
            package_id=package_id,
            instance_id=instance_id,
            status="active",
            started_at=now,
            last_seen_at=now,
        )
        headers = [str(value).strip() for value in self.sessions.row_values(1)]
        data = {
            "session_id": session.session_id,
            "run_id": session.run_id,
            "user_id": session.user_id,
            "package_id": session.package_id,
            "instance_id": session.instance_id,
            "status": session.status,
            "started_at": session.started_at,
            "last_seen_at": session.last_seen_at,
            "ended_at": session.ended_at,
        }
        self.sessions.append_row(
            [data.get(header, "") for header in headers],
            value_input_option="RAW",
        )
        return session

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
            run_id=run_id,
            session_id=session_id,
            user_id=user_id,
            package_id=package_id,
            sequence=sequence,
            role=role,
            content=content,
            block_id=block_id,
            beat_id=beat_id,
            speaker_id=speaker_id,
            metadata=metadata,
        )
        if role == "assistant" and isinstance(metadata, dict):
            self._persist_pending_memories(
                run_id=run_id,
                source_beat_id=beat_id,
                metadata=metadata,
            )

    def _persist_pending_memories(
        self,
        *,
        run_id: str,
        source_beat_id: str,
        metadata: dict[str, Any],
    ) -> None:
        pilot_state = metadata.get("pilot_state")
        if not isinstance(pilot_state, dict):
            return
        facts = pilot_state.get("facts")
        if not isinstance(facts, dict):
            return
        raw = str(facts.get("_pending_memory_writes", "") or "")
        for memory_id in (item.strip() for item in raw.split(",")):
            if not memory_id:
                continue
            self.runs.append_run_memory(
                run_id=run_id,
                memory_id=memory_id,
                source_beat_id=source_beat_id,
            )

    def list_run_memory_ids(self, *, run_id: str) -> list[str]:
        values = {
            str(row.get("memory_id", "")).strip()
            for row in self.runs.memories.records()
            if str(row.get("run_id", "")).strip() == run_id
            and str(row.get("memory_id", "")).strip()
        }
        return sorted(values)

    def list_interactions(self, *, run_id: str, limit: int = 100) -> list[dict[str, object]]:
        requested_limit = max(1, min(int(limit), MAX_RECOVERED_INTERACTIONS))
        rows = [
            row
            for row in self.interactions.table.records()
            if str(row.get("run_id", "")).strip() == run_id
        ]
        rows.sort(key=lambda row: int(row.get("sequence", 0) or 0))
        rows = rows[-requested_limit:]

        result: list[dict[str, object]] = []
        for row in rows:
            metadata: dict[str, object] = {}
            raw_metadata = str(row.get("metadata_json", "") or "")
            if raw_metadata:
                try:
                    parsed = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    parsed = {}
                if isinstance(parsed, dict):
                    metadata = dict(parsed)
            result.append(
                {
                    "role": str(row.get("role", "assistant")),
                    "content": str(row.get("content", "")),
                    "sequence": int(row.get("sequence", 0) or 0),
                    "block_id": str(row.get("block_id", "")),
                    "beat_id": str(row.get("beat_id", "")),
                    **metadata,
                }
            )

        active_ids = self.list_run_memory_ids(run_id=run_id)
        if active_ids:
            for message in reversed(result):
                pilot_state = message.get("pilot_state")
                if not isinstance(pilot_state, dict):
                    continue
                facts = pilot_state.setdefault("facts", {})
                if isinstance(facts, dict):
                    facts["_active_memory_ids"] = ",".join(active_ids)
                break
        return result

    def update_run_progress(
        self,
        *,
        run: StoryRun,
        block_id: str,
        beat_id: str,
    ) -> StoryRun:
        run.current_block_id = block_id or run.current_block_id
        run.current_beat_id = beat_id or run.current_beat_id
        return self.runs.update_run(run=run, expected_version=run.state_version)
