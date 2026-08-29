from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import gspread
from gspread import Spreadsheet

from narrative_v2.models import StoryRun
from narrative_v2.repository import RuntimeConflictError
from persistence.models import new_id, utc_now_iso
from persistence.v2_google_sheets import (
    _SheetTable,
    GoogleSheetsNarrativeInteractionRepository,
    GoogleSheetsStoryRunRepository,
)


MAX_RECOVERED_INTERACTIONS = 500
RUNTIME_REPOSITORY_CONTRACT_VERSION = 5


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
        self._session_table = _SheetTable(spreadsheet, "SESSIONS")
        self.sessions = self._session_table.worksheet

    @classmethod
    def from_service_account(
        cls,
        *,
        credentials: dict[str, Any],
        spreadsheet_id: str,
    ) -> "GoogleSheetsV2RuntimeRepository":
        # O cliente com backoff respeita Retry-After/429 do Google Sheets em
        # picos breves, em vez de transformar imediatamente a cota transitória
        # em erro visível para o usuário.
        client = gspread.service_account_from_dict(
            credentials,
            http_client=gspread.BackOffHTTPClient,
        )
        return cls(client.open_by_key(spreadsheet_id))

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        return self.runs.get_active_run(user_id=user_id, package_id=package_id)

    def get_run(self, *, run_id: str) -> StoryRun | None:
        found = self.runs.runs.find("run_id", run_id)
        if found is None:
            return None
        _row_number, row = found
        return self.runs._from_row(row)

    @staticmethod
    def _assert_interaction_owner(
        row: dict[str, Any],
        *,
        run_id: str,
        user_id: str,
        package_id: str,
    ) -> None:
        row_user_id = str(row.get("user_id", "") or "").strip()
        row_package_id = str(row.get("package_id", "") or "").strip()
        if row_user_id != user_id or row_package_id != package_id:
            raise RuntimeConflictError(
                "INTERACTIONS contém uma linha com run_id correto, mas proprietário "
                "incompatível: "
                f"run_id={run_id}, esperado=({user_id}, {package_id}), "
                f"encontrado=({row_user_id}, {row_package_id})."
            )

    def _interaction_rows_for_owner(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
    ) -> list[dict[str, Any]]:
        """Lê uma run usando a chave composta run + usuário + pacote e falha fechado.

        ``run_id`` continua sendo o identificador principal da execução, porém a
        recuperação nunca confia apenas nele. Toda linha correspondente precisa
        pertencer também ao mesmo usuário autenticado e ao mesmo ``package_id``.
        """

        clean_run_id = str(run_id or "").strip()
        clean_user_id = str(user_id or "").strip()
        clean_package_id = str(package_id or "").strip()
        if not clean_run_id or not clean_user_id or not clean_package_id:
            raise RuntimeConflictError(
                "Recuperação de INTERACTIONS exige run_id, user_id e package_id."
            )

        rows: list[dict[str, Any]] = []
        for raw in self.interactions.table.records():
            row = dict(raw)
            if str(row.get("run_id", "") or "").strip() != clean_run_id:
                continue
            self._assert_interaction_owner(
                row,
                run_id=clean_run_id,
                user_id=clean_user_id,
                package_id=clean_package_id,
            )
            rows.append(row)
        return rows

    def _was_false_message_ending(self, run: StoryRun) -> bool:
        if run.status != "terminated" or run.ending_code != "mary_lost_interest":
            return False

        rows = [
            row
            for row in self._interaction_rows_for_owner(
                run_id=run.run_id,
                user_id=run.user_id,
                package_id=run.package_id,
            )
            if str(row.get("role", "")).strip() == "assistant"
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
        existing = [
            dict(row)
            for row in self._session_table.records()
            if str(row.get("run_id", "") or "").strip() == run_id
            and str(row.get("user_id", "") or "").strip() == user_id
            and str(row.get("package_id", "") or "").strip() == package_id
            and str(row.get("instance_id", "") or "").strip() == instance_id
            and str(row.get("status", "") or "").strip() == "active"
        ]
        if existing:
            existing.sort(
                key=lambda row: str(
                    row.get("last_seen_at", "") or row.get("started_at", "") or ""
                ),
                reverse=True,
            )
            row = existing[0]
            return RuntimeSession(
                session_id=str(row.get("session_id", "") or ""),
                run_id=str(row.get("run_id", "") or ""),
                user_id=str(row.get("user_id", "") or ""),
                package_id=str(row.get("package_id", "") or ""),
                instance_id=str(row.get("instance_id", "") or ""),
                status=str(row.get("status", "") or "active"),
                started_at=str(row.get("started_at", "") or ""),
                last_seen_at=str(row.get("last_seen_at", "") or ""),
                ended_at=str(row.get("ended_at", "") or ""),
            )

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
        self._session_table.append(data)
        return session

    def _existing_interaction(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        sequence: int,
        role: str,
    ) -> dict[str, Any] | None:
        for raw in self.interactions.table.records():
            row = dict(raw)
            if str(row.get("run_id", "")).strip() != run_id:
                continue
            self._assert_interaction_owner(
                row,
                run_id=run_id,
                user_id=user_id,
                package_id=package_id,
            )
            if int(row.get("sequence", 0) or 0) != int(sequence):
                continue
            if str(row.get("role", "")).strip() != role:
                continue
            return row
        return None

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
        existing = self._existing_interaction(
            run_id=run_id,
            user_id=user_id,
            package_id=package_id,
            sequence=sequence,
            role=role,
        )
        if existing is not None:
            existing_content = str(existing.get("content", "") or "")
            if existing_content != str(content or ""):
                raise RuntimeConflictError(
                    f"Interação concorrente incompatível na run {run_id}, "
                    f"sequência={sequence}, role={role}."
                )
            return

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
        runs = getattr(self, "runs", None)
        memories = getattr(runs, "memories", None)
        if memories is None:
            return []
        values = {
            str(row.get("memory_id", "")).strip()
            for row in memories.records()
            if str(row.get("run_id", "")).strip() == run_id
            and str(row.get("memory_id", "")).strip()
        }
        return sorted(values)

    def list_interactions(self, *, run_id: str, limit: int = 100) -> list[dict[str, object]]:
        run = self.get_run(run_id=run_id)
        if run is None:
            raise RuntimeConflictError(
                f"Não é possível recuperar INTERACTIONS de run inexistente: {run_id}."
            )

        requested_limit = max(1, min(int(limit), MAX_RECOVERED_INTERACTIONS))
        rows = self._interaction_rows_for_owner(
            run_id=run.run_id,
            user_id=run.user_id,
            package_id=run.package_id,
        )
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

        active_ids = self.list_run_memory_ids(run_id=run.run_id)
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

    def persist_frame_reveal(
        self,
        *,
        run_id: str,
        user_id: str,
        package_id: str,
        frame_id: str,
        revealed_entries: int,
    ) -> int:
        """Atualiza o checkpoint visual na interação assistente do quadro atual."""

        rows = self._interaction_rows_for_owner(
            run_id=run_id,
            user_id=user_id,
            package_id=package_id,
        )
        indexed = list(enumerate(rows))
        indexed.sort(key=lambda item: int(item[1].get("sequence", 0) or 0), reverse=True)
        for _index, row in indexed:
            if str(row.get("role", "")) != "assistant":
                continue
            content = str(row.get("content", "") or "")
            from services.novel_frame_reveal import frame_entry_count, frame_id as content_frame_id

            if content_frame_id(content) != frame_id:
                continue
            total = frame_entry_count(content)
            value = min(max(0, int(revealed_entries)), total)
            raw = str(row.get("metadata_json", "") or "")
            try:
                metadata = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}
            previous = int(metadata.get("flet_revealed_entries", 0) or 0)
            metadata["flet_revealed_entries"] = max(previous, value)
            updated = dict(row)
            updated["metadata_json"] = json.dumps(
                metadata, ensure_ascii=False, separators=(",", ":")
            )
            found = self.interactions.table.find("interaction_id", str(row.get("interaction_id", "")))
            if found is None:
                raise RuntimeConflictError("Interação do quadro não foi encontrada para checkpoint.")
            self.interactions.table.replace(found[0], updated)
            return int(metadata["flet_revealed_entries"])
        raise RuntimeConflictError("Quadro atual não encontrado em INTERACTIONS.")

    def update_run_progress(
        self,
        *,
        run: StoryRun,
        block_id: str,
        beat_id: str,
    ) -> StoryRun:
        desired_block_id = block_id or run.current_block_id
        desired_beat_id = beat_id or run.current_beat_id
        run.current_block_id = desired_block_id
        run.current_beat_id = desired_beat_id
        try:
            return self.runs.update_run(run=run, expected_version=run.state_version)
        except RuntimeConflictError:
            current = self.get_run(run_id=run.run_id)
            if current is None:
                raise
            if (
                current.current_block_id == desired_block_id
                and current.current_beat_id == desired_beat_id
            ):
                return current
            current.current_block_id = desired_block_id
            current.current_beat_id = desired_beat_id
            return self.runs.update_run(
                run=current,
                expected_version=current.state_version,
            )
