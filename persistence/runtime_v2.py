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

    def list_interactions(self, *, run_id: str, limit: int = 100) -> list[dict[str, object]]:
        rows = self.interactions.list_recent_interactions(run_id=run_id, limit=min(limit, 20))
        result: list[dict[str, object]] = []
        for row in rows:
            metadata: dict[str, object] = {}
            raw_metadata = str(row.get("metadata_json", "") or "")
            if raw_metadata:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    metadata = dict(parsed)
            result.append(
                {
                    "role": str(row.get("role", "assistant")),
                    "content": str(row.get("content", "")),
                    "sequence": int(row.get("sequence", 0) or 0),
                    **metadata,
                }
            )
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
