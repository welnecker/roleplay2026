from __future__ import annotations

from typing import Any

from persistence.runtime_v2 import GoogleSheetsV2RuntimeRepository


class EditorialGoogleSheetsV2RuntimeRepository(GoogleSheetsV2RuntimeRepository):
    """Adapta a persistência V2 ao contrato canônico `editorial_*`.

    O formato `pilot_*` permanece somente como leitura de compatibilidade para
    interações gravadas antes da migração do runtime editorial.
    """

    def _persist_pending_memories(
        self,
        *,
        run_id: str,
        source_beat_id: str,
        metadata: dict[str, Any],
    ) -> None:
        editorial_state = metadata.get("editorial_state")
        legacy_state = metadata.get("pilot_state")
        state = editorial_state if isinstance(editorial_state, dict) else legacy_state
        if not isinstance(state, dict):
            return

        facts = state.get("facts")
        if not isinstance(facts, dict):
            return

        canonical_source = str(metadata.get("editorial_node", "") or "").strip()
        resolved_source = canonical_source or str(source_beat_id or "").strip()
        raw = str(facts.get("_pending_memory_writes", "") or "")
        for memory_id in (item.strip() for item in raw.split(",")):
            if not memory_id:
                continue
            self.runs.append_run_memory(
                run_id=run_id,
                memory_id=memory_id,
                source_beat_id=resolved_source,
            )


__all__ = ["EditorialGoogleSheetsV2RuntimeRepository"]
