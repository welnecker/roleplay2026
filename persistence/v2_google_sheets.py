from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import gspread
from gspread import Spreadsheet, Worksheet

from narrative_v2.models import RunCredit, StoryRun
from narrative_v2.repository import RuntimeConflictError
from persistence.models import new_id, utc_now_iso


class _SheetTable:
    def __init__(self, spreadsheet: Spreadsheet, sheet_name: str) -> None:
        self.spreadsheet = spreadsheet
        self.sheet_name = sheet_name
        self._worksheet: Worksheet | None = None

    @property
    def worksheet(self) -> Worksheet:
        if self._worksheet is None:
            self._worksheet = self.spreadsheet.worksheet(self.sheet_name)
        return self._worksheet

    def records(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.worksheet.get_all_records(default_blank="")]

    def find(self, key: str, value: str) -> tuple[int, dict[str, Any]] | None:
        headers = self.headers()
        if key not in headers:
            raise RuntimeError(f"Coluna ausente em {self.sheet_name}: {key}")
        for row_number, row in enumerate(self.worksheet.get_all_records(default_blank=""), start=2):
            if str(row.get(key, "")).strip() == value:
                return row_number, dict(row)
        return None

    def append(self, data: dict[str, Any]) -> None:
        headers = self.headers()
        self.worksheet.append_row(
            [data.get(header, "") for header in headers],
            value_input_option="RAW",
        )

    def replace(self, row_number: int, data: dict[str, Any]) -> None:
        headers = self.headers()
        self.worksheet.update(
            range_name=f"A{row_number}",
            values=[[data.get(header, "") for header in headers]],
            value_input_option="RAW",
        )

    def headers(self) -> list[str]:
        return [str(item).strip() for item in self.worksheet.row_values(1)]


class GoogleSheetsStoryCreditRepository:
    """Créditos de uma execução, armazenados em ROLEPLAY_ACCOUNTS_BILLING."""

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.table = _SheetTable(spreadsheet, "STORY_CREDITS")

    def create_credit(
        self,
        *,
        user_id: str,
        package_id: str,
        payment_id: str,
    ) -> RunCredit:
        payment_id = payment_id.strip()
        if not payment_id:
            raise ValueError("payment_id é obrigatório.")

        existing = next(
            (
                row
                for row in self.table.records()
                if str(row.get("payment_id", "")).strip() == payment_id
                and str(row.get("package_id", "")).strip() == package_id
            ),
            None,
        )
        if existing is not None:
            credit = self._from_row(existing)
            if credit.user_id != user_id:
                raise RuntimeConflictError(
                    f"Pagamento {payment_id} já está associado a outro usuário."
                )
            return credit

        credit = RunCredit(
            credit_id=new_id("credit"),
            user_id=user_id,
            package_id=package_id,
            payment_id=payment_id,
            status="available",
            created_at=utc_now_iso(),
        )
        self.table.append(self._to_row(credit))
        return credit

    def get_available_credit(
        self,
        *,
        user_id: str,
        package_id: str,
    ) -> RunCredit | None:
        candidates = [
            self._from_row(row)
            for row in self.table.records()
            if str(row.get("user_id", "")).strip() == user_id
            and str(row.get("package_id", "")).strip() == package_id
            and str(row.get("status", "")).strip() == "available"
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda credit: credit.created_at)
        return candidates[0]

    def consume_credit(self, *, credit_id: str, run_id: str) -> RunCredit:
        found = self.table.find("credit_id", credit_id)
        if found is None:
            raise KeyError(f"Crédito não encontrado: {credit_id}")
        row_number, row = found
        current = self._from_row(row)
        if current.status == "consumed" and current.run_id == run_id:
            return current
        if current.status != "available":
            raise RuntimeConflictError(
                f"Crédito {credit_id} não está disponível: {current.status}."
            )
        updated = RunCredit(
            credit_id=current.credit_id,
            user_id=current.user_id,
            package_id=current.package_id,
            payment_id=current.payment_id,
            status="consumed",
            run_id=run_id,
            created_at=current.created_at,
            consumed_at=utc_now_iso(),
        )
        self.table.replace(row_number, self._to_row(updated))
        return updated

    @staticmethod
    def _from_row(row: dict[str, Any]) -> RunCredit:
        return RunCredit(
            credit_id=str(row.get("credit_id", "")),
            user_id=str(row.get("user_id", "")),
            package_id=str(row.get("package_id", "")),
            payment_id=str(row.get("payment_id", "")),
            status=str(row.get("status", "available")),  # type: ignore[arg-type]
            run_id=str(row.get("run_id", "")),
            created_at=str(row.get("created_at", "")),
            consumed_at=str(row.get("consumed_at", "")),
        )

    @staticmethod
    def _to_row(credit: RunCredit) -> dict[str, Any]:
        row = asdict(credit)
        row["revoked_at"] = ""
        return row


class GoogleSheetsStoryRunRepository:
    """Execuções e memórias, armazenadas em ROLEPLAY_RUNTIME."""

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.runs = _SheetTable(spreadsheet, "STORY_RUNS")
        self.memories = _SheetTable(spreadsheet, "RUN_MEMORIES")

    def create_run(
        self,
        *,
        credit: RunCredit,
        script_version: str,
        first_block_id: str,
        first_beat_id: str,
    ) -> StoryRun:
        existing = self.get_active_run(
            user_id=credit.user_id,
            package_id=credit.package_id,
        )
        if existing is not None:
            return existing
        if credit.status not in {"available", "consumed"}:
            raise RuntimeConflictError(
                f"Crédito {credit.credit_id} não pode iniciar uma run: {credit.status}."
            )
        now = utc_now_iso()
        run = StoryRun(
            run_id=new_id("run"),
            credit_id=credit.credit_id,
            user_id=credit.user_id,
            package_id=credit.package_id,
            script_version=script_version,
            current_block_id=first_block_id,
            current_beat_id=first_beat_id,
            status="active",
            state_version=1,
            started_at=now,
            updated_at=now,
        )
        self.runs.append(self._to_row(run))
        return run

    def get_active_run(self, *, user_id: str, package_id: str) -> StoryRun | None:
        candidates = [
            self._from_row(row)
            for row in self.runs.records()
            if str(row.get("user_id", "")).strip() == user_id
            and str(row.get("package_id", "")).strip() == package_id
            and str(row.get("status", "")).strip() == "active"
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda run: run.updated_at, reverse=True)
        return candidates[0]

    def update_run(self, *, run: StoryRun, expected_version: int) -> StoryRun:
        found = self.runs.find("run_id", run.run_id)
        if found is None:
            raise KeyError(f"Run não encontrada: {run.run_id}")
        row_number, row = found
        current = self._from_row(row)
        if current.state_version != expected_version:
            raise RuntimeConflictError(
                f"Versão concorrente na run {run.run_id}: "
                f"esperada={expected_version}, atual={current.state_version}."
            )
        updated = StoryRun(
            run_id=run.run_id,
            credit_id=run.credit_id,
            user_id=run.user_id,
            package_id=run.package_id,
            script_version=run.script_version,
            current_block_id=run.current_block_id,
            current_beat_id=run.current_beat_id,
            status=run.status,
            ending_code=run.ending_code,
            state_version=expected_version + 1,
            permanent_memory_ids=list(run.permanent_memory_ids),
            started_at=current.started_at or run.started_at,
            ended_at=run.ended_at,
            updated_at=utc_now_iso(),
        )
        self.runs.replace(row_number, self._to_row(updated))
        return updated

    def append_run_memory(
        self,
        *,
        run_id: str,
        memory_id: str,
        source_beat_id: str,
    ) -> None:
        duplicate = next(
            (
                row
                for row in self.memories.records()
                if str(row.get("run_id", "")).strip() == run_id
                and str(row.get("memory_id", "")).strip() == memory_id
            ),
            None,
        )
        if duplicate is not None:
            return
        self.memories.append(
            {
                "run_memory_id": new_id("rmem"),
                "run_id": run_id,
                "memory_id": memory_id,
                "source_beat_id": source_beat_id,
                "created_at": utc_now_iso(),
            }
        )

    @staticmethod
    def _from_row(row: dict[str, Any]) -> StoryRun:
        raw_memories = str(row.get("permanent_memory_ids_json", "") or "")
        memories: list[str] = []
        if raw_memories:
            parsed = json.loads(raw_memories)
            if isinstance(parsed, list):
                memories = [str(value) for value in parsed if str(value).strip()]
        return StoryRun(
            run_id=str(row.get("run_id", "")),
            credit_id=str(row.get("credit_id", "")),
            user_id=str(row.get("user_id", "")),
            package_id=str(row.get("package_id", "")),
            script_version=str(row.get("script_version", "")),
            current_block_id=str(row.get("current_block_id", "")),
            current_beat_id=str(row.get("current_beat_id", "")),
            status=str(row.get("status", "active")),  # type: ignore[arg-type]
            ending_code=str(row.get("ending_code", "")),
            state_version=int(row.get("state_version", 1) or 1),
            permanent_memory_ids=memories,
            started_at=str(row.get("started_at", "")),
            ended_at=str(row.get("ended_at", "")),
            updated_at=str(row.get("updated_at", "")),
        )

    @staticmethod
    def _to_row(run: StoryRun) -> dict[str, Any]:
        row = asdict(run)
        row["permanent_memory_ids_json"] = json.dumps(
            run.permanent_memory_ids,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        row.pop("permanent_memory_ids")
        return row


class GoogleSheetsNarrativeInteractionRepository:
    """Histórico recente e auditoria, armazenados em ROLEPLAY_RUNTIME."""

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.table = _SheetTable(spreadsheet, "INTERACTIONS")

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
        self.table.append(
            {
                "interaction_id": new_id("int"),
                "session_id": session_id,
                "run_id": run_id,
                "user_id": user_id,
                "package_id": package_id,
                "sequence": sequence,
                "role": role,
                "speaker_id": speaker_id,
                "content": content,
                "block_id": block_id,
                "beat_id": beat_id,
                "user_intent": user_intent,
                "beat_consumed": "true" if beat_consumed else "false",
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "created_at": utc_now_iso(),
                "metadata_json": json.dumps(
                    metadata or {},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        )

    def list_recent_interactions(
        self,
        *,
        run_id: str,
        limit: int = 6,
    ) -> list[dict[str, object]]:
        safe_limit = max(1, min(int(limit), 20))
        rows = [
            row
            for row in self.table.records()
            if str(row.get("run_id", "")).strip() == run_id
        ]
        rows.sort(key=lambda row: int(row.get("sequence", 0) or 0))
        return rows[-safe_limit:]


class GoogleSheetsNarrativeRepositories:
    """Agrupa os repositórios que compartilham as duas planilhas operacionais."""

    def __init__(self, *, accounts_billing: Spreadsheet, runtime: Spreadsheet) -> None:
        self.credits = GoogleSheetsStoryCreditRepository(accounts_billing)
        self.runs = GoogleSheetsStoryRunRepository(runtime)
        self.interactions = GoogleSheetsNarrativeInteractionRepository(runtime)

    @classmethod
    def from_service_account(
        cls,
        *,
        credentials: dict[str, Any],
        accounts_billing_spreadsheet_id: str,
        runtime_spreadsheet_id: str,
    ) -> "GoogleSheetsNarrativeRepositories":
        client = gspread.service_account_from_dict(credentials)
        return cls(
            accounts_billing=client.open_by_key(accounts_billing_spreadsheet_id),
            runtime=client.open_by_key(runtime_spreadsheet_id),
        )
