from __future__ import annotations

from pathlib import Path


def test_runtime_persistence_reads_canonical_editorial_end_keys() -> None:
    source = Path("services/runtime_persistence.py").read_text(encoding="utf-8")

    assert 'assistant_metadata.get("editorial_run_status")' in source
    assert 'assistant_metadata.get("editorial_ending_code")' in source
    assert 'assistant_metadata.get("pilot_run_status")' in source
    assert 'assistant_metadata.get("pilot_ending_code")' in source
