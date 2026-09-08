from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SpreadsheetIds:
    """Identificadores das três planilhas da arquitetura narrativa v2."""

    accounts_billing: str
    runtime: str
    editorial: str

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID", self.accounts_billing),
                ("ROLEPLAY_RUNTIME_SPREADSHEET_ID", self.runtime),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError(
                "IDs de planilha ausentes: " + ", ".join(missing)
            )


def read_spreadsheet_ids(secrets: Any) -> SpreadsheetIds:
    """Lê os IDs sem criar conexões ou modificar o runtime atual."""

    runtime_id = str(
        secrets.get("ROLEPLAY_RUNTIME_SPREADSHEET_ID", "") or ""
    ).strip()
    ids = SpreadsheetIds(
        accounts_billing=str(
            secrets.get("ROLEPLAY_ACCOUNTS_BILLING_SPREADSHEET_ID", "") or ""
        ).strip(),
        runtime=runtime_id,
        editorial=str(
            secrets.get("ROLEPLAY_EDITORIAL_SPREADSHEET_ID", "") or runtime_id
        ).strip(),
    )
    ids.validate()
    return ids
