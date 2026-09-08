from __future__ import annotations

from flet_client.frame_view import FrameStageCursor


def test_cursor_opens_on_latest_revealed_position() -> None:
    cursor = FrameStageCursor()

    assert cursor.latest(4) == 3
    assert cursor.position == 3


def test_previous_and_next_only_move_local_visual_position() -> None:
    cursor = FrameStageCursor(position=3)

    assert cursor.previous(4) == 2
    assert cursor.previous(4) == 1
    assert cursor.next(4) == 2
    assert cursor.position == 2


def test_cursor_never_crosses_revealed_visual_bounds() -> None:
    cursor = FrameStageCursor(position=0)

    assert cursor.previous(4) == 0
    cursor.position = 99
    assert cursor.clamp(4) == 3
    assert cursor.next(4) == 3


def test_cursor_handles_empty_stage_without_negative_position() -> None:
    cursor = FrameStageCursor(position=5)

    assert cursor.clamp(0) == 0
    assert cursor.previous(0) == 0
    assert cursor.next(0) == 0
