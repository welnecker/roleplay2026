from __future__ import annotations

from typing import Any, Iterable, Protocol


class RunMemoryWriter(Protocol):
    def append_run_memory(
        self,
        *,
        run_id: str,
        memory_id: str,
        source_beat_id: str,
    ) -> None: ...


class RuntimeWithMemories(Protocol):
    runs: RunMemoryWriter


def list_run_memory_ids(repository: Any, *, run_id: str) -> list[str]:
    """Lê ativações existentes sem duplicar conteúdo editorial na planilha."""

    memory_table = getattr(getattr(repository, "runs", None), "memories", None)
    if memory_table is None:
        return []
    rows = memory_table.records()
    values = {
        str(row.get("memory_id", "")).strip()
        for row in rows
        if str(row.get("run_id", "")).strip() == run_id
        and str(row.get("memory_id", "")).strip()
    }
    return sorted(values)


def apply_memory_writes(
    repository: RuntimeWithMemories,
    *,
    run_id: str,
    source_beat_id: str,
    memory_ids: Iterable[str],
) -> list[str]:
    """Ativa, de forma idempotente, as memórias declaradas pelo beat consumido."""

    written: list[str] = []
    for raw_memory_id in memory_ids:
        memory_id = str(raw_memory_id).strip()
        if not memory_id:
            continue
        repository.runs.append_run_memory(
            run_id=run_id,
            memory_id=memory_id,
            source_beat_id=source_beat_id,
        )
        written.append(memory_id)
    return written
