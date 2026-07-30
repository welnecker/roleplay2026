from __future__ import annotations

import json
from typing import Any

import gspread
from gspread import Spreadsheet, Worksheet

from persistence.models import utc_now_iso
from persistence.v2_schemas import EDITORIAL_SCHEMAS


class GoogleSheetsEditorialRepository:
    """Fonte editorial única da história publicada."""

    def __init__(self, spreadsheet: Spreadsheet) -> None:
        self.spreadsheet = spreadsheet
        self._worksheets: dict[str, Worksheet] = {}

    @classmethod
    def from_service_account(
        cls,
        *,
        credentials: dict[str, Any],
        spreadsheet_id: str,
    ) -> "GoogleSheetsEditorialRepository":
        client = gspread.service_account_from_dict(credentials)
        return cls(client.open_by_key(spreadsheet_id))

    def ensure_schema(self) -> None:
        for name, headers in EDITORIAL_SCHEMAS.items():
            worksheet = self._get_or_create(name, cols=len(headers))
            current = tuple(str(value).strip() for value in worksheet.row_values(1))
            if not current:
                worksheet.append_row(list(headers), value_input_option="RAW")
            elif current != headers:
                raise RuntimeError(
                    f"Cabeçalhos incompatíveis na aba {name}: esperado={headers}, atual={current}"
                )

    def seed_pilot(self, *, package_id: str, title: str, raw: dict[str, Any]) -> None:
        """Publica o piloto apenas quando a história ainda não existe na planilha."""

        if self.get_story(package_id) is not None:
            return

        now = utc_now_iso()
        scene = dict(raw.get("scene") or {})
        beats = [item for item in scene.get("beats", []) if isinstance(item, dict)]
        endings = [item for item in scene.get("endings", []) if isinstance(item, dict)]
        first_beat_id = str(beats[0].get("beat_id", "collision")) if beats else "collision"
        script_version = str(raw.get("script_version", "0.1.0-pilot"))

        self._append(
            "STORIES",
            {
                "package_id": package_id,
                "script_version": script_version,
                "title": title,
                "introduction": str(scene.get("objective", "")),
                "character_id": "mary",
                "first_block_id": str(scene.get("scene_id", "supermercado_pilot")),
                "first_beat_id": first_beat_id,
                "status": "active",
                "updated_at": now,
            },
        )
        self._append(
            "CHARACTERS",
            {
                "package_id": package_id,
                "character_id": "mary",
                "name": "Mary",
                "age": 25,
                "physical_profile": "mulher adulta brasileira",
                "psychological_profile": "desejos próprios; reciprocidade; autonomia para encerrar",
                "speech_style": "pensamento curto, fala direta e onomatopeia; sem narração de ações",
                "updated_at": now,
            },
        )
        self._append(
            "BLOCKS",
            {
                "package_id": package_id,
                "block_id": str(scene.get("scene_id", "supermercado_pilot")),
                "order": 1,
                "title": str(scene.get("location", "Supermercado")),
                "entry_beat_id": first_beat_id,
                "max_movements_per_response": 1,
                "max_questions_per_response": 1,
                "rules_json": self._json(
                    {
                        "runtime_contract": raw.get("runtime_contract") or {},
                        "engagement_policy": raw.get("engagement_policy") or {},
                        "mary_state": raw.get("mary_state") or {},
                        "scene": {
                            "scene_id": scene.get("scene_id", "supermercado_pilot"),
                            "location": scene.get("location", ""),
                            "objective": scene.get("objective", ""),
                        },
                    }
                ),
                "updated_at": now,
            },
        )

        for order, beat in enumerate(beats, start=1):
            self._append(
                "BEATS",
                {
                    "package_id": package_id,
                    "beat_id": str(beat.get("beat_id", "")),
                    "block_id": str(scene.get("scene_id", "supermercado_pilot")),
                    "order": order,
                    "type": "dialogue",
                    "required_movement": self._json(beat),
                    "canonical_line": "",
                    "dramatic_direction": str(beat.get("objective", "")),
                    "next_beat_id": str(beat.get("terminal_transition", "")),
                    "max_questions": 1,
                    "max_sentences": "",
                    "memory_writes_json": "[]",
                    "allowed_transitions_json": self._json(beat.get("on_user") or {}),
                    "ending_json": "",
                    "status": "active",
                    "updated_at": now,
                },
            )

        memory_ids: set[str] = set()
        for order, ending in enumerate(endings, start=len(beats) + 1):
            ending_id = str(ending.get("ending_id", ""))
            writes = [str(item) for item in ending.get("memory_writes", []) if str(item).strip()]
            memory_ids.update(writes)
            self._append(
                "BEATS",
                {
                    "package_id": package_id,
                    "beat_id": ending_id,
                    "block_id": str(scene.get("scene_id", "supermercado_pilot")),
                    "order": order,
                    "type": "ending",
                    "required_movement": "",
                    "canonical_line": str((ending.get("visible_delivery") or {}).get("text", "")),
                    "dramatic_direction": "",
                    "next_beat_id": "",
                    "max_questions": 0,
                    "max_sentences": 1,
                    "memory_writes_json": self._json(writes),
                    "allowed_transitions_json": "{}",
                    "ending_json": self._json(ending),
                    "status": "active",
                    "updated_at": now,
                },
            )

        for memory_id in sorted(memory_ids):
            self._append(
                "MEMORIES",
                {
                    "package_id": package_id,
                    "memory_id": memory_id,
                    "memory_text": memory_id.replace("_", " "),
                    "source_beat_id": "",
                    "status": "active",
                    "updated_at": now,
                },
            )

    def get_story(self, package_id: str) -> dict[str, Any] | None:
        return next(
            (
                row
                for row in self._records("STORIES")
                if str(row.get("package_id", "")).strip() == package_id
                and str(row.get("status", "active")).strip() == "active"
            ),
            None,
        )

    def load_pilot_raw(self, package_id: str) -> dict[str, Any]:
        story = self.get_story(package_id)
        if story is None:
            raise KeyError(f"História editorial não encontrada: {package_id}")
        blocks = [
            row
            for row in self._records("BLOCKS")
            if str(row.get("package_id", "")).strip() == package_id
        ]
        if not blocks:
            raise RuntimeError(f"Nenhum bloco editorial encontrado para {package_id}.")
        blocks.sort(key=lambda row: int(row.get("order", 0) or 0))
        rules = self._parse_json(blocks[0].get("rules_json"))

        rows = [
            row
            for row in self._records("BEATS")
            if str(row.get("package_id", "")).strip() == package_id
            and str(row.get("status", "active")).strip() == "active"
        ]
        rows.sort(key=lambda row: int(row.get("order", 0) or 0))
        beats: list[dict[str, Any]] = []
        endings: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("type", "")) == "ending":
                ending = self._parse_json(row.get("ending_json"))
                if ending:
                    endings.append(ending)
            else:
                beat = self._parse_json(row.get("required_movement"))
                if beat:
                    beats.append(beat)

        scene_meta = dict(rules.get("scene") or {})
        return {
            "format_version": 1,
            "status": "published",
            "package_id": package_id,
            "script_version": str(story.get("script_version", "")),
            "runtime_contract": rules.get("runtime_contract") or {},
            "engagement_policy": rules.get("engagement_policy") or {},
            "mary_state": rules.get("mary_state") or {},
            "scene": {
                **scene_meta,
                "beats": beats,
                "endings": endings,
            },
        }

    def _worksheet(self, name: str) -> Worksheet:
        if name not in self._worksheets:
            self._worksheets[name] = self.spreadsheet.worksheet(name)
        return self._worksheets[name]

    def _get_or_create(self, name: str, *, cols: int) -> Worksheet:
        try:
            return self._worksheet(name)
        except gspread.WorksheetNotFound:
            worksheet = self.spreadsheet.add_worksheet(title=name, rows=1000, cols=cols)
            self._worksheets[name] = worksheet
            return worksheet

    def _records(self, name: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self._worksheet(name).get_all_records(default_blank="")]

    def _append(self, name: str, data: dict[str, Any]) -> None:
        worksheet = self._worksheet(name)
        headers = [str(item).strip() for item in worksheet.row_values(1)]
        worksheet.append_row([data.get(header, "") for header in headers], value_input_option="RAW")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _parse_json(value: Any) -> dict[str, Any]:
        if not value:
            return {}
        parsed = json.loads(str(value))
        return dict(parsed) if isinstance(parsed, dict) else {}
