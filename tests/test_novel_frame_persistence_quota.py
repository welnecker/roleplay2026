from __future__ import annotations

from roleplay.models import StoryState
from services.runtime_persistence import should_checkpoint_run_progress


def _state(step: int, *, finished: bool = False) -> StoryState:
    return StoryState(step_index=step, consumed_orders=list(range(1, step + 1)), finished=finished)


def test_visual_novel_faz_checkpoint_a_cada_cinco_quadros() -> None:
    metadata = {"novel_frame": True}

    assert not should_checkpoint_run_progress(state=_state(1), assistant_metadata=metadata)
    assert not should_checkpoint_run_progress(state=_state(4), assistant_metadata=metadata)
    assert should_checkpoint_run_progress(state=_state(5), assistant_metadata=metadata)
    assert should_checkpoint_run_progress(state=_state(10), assistant_metadata=metadata)


def test_final_e_runtime_legado_continuam_atualizando_a_run() -> None:
    assert should_checkpoint_run_progress(
        state=_state(3, finished=True),
        assistant_metadata={"novel_frame": True},
    )
    assert should_checkpoint_run_progress(
        state=_state(3),
        assistant_metadata={"novel_frame": False},
    )
