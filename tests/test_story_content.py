from __future__ import annotations

from pathlib import Path

import pytest

from packages.story_content import StoryContentError, load_story_content


VALID_STORY = """
story_id: example_story
title: Example Story
entry_route: principal
routes:
  - id: principal
    beats:
      - id: opening
        movements:
          - order: 2
            content: Second movement
          - order: 1
            content: First movement
"""


def write_story(root: Path, content: str = VALID_STORY) -> Path:
    source = root / "story.yaml"
    source.write_text(content, encoding="utf-8")
    return source


def test_load_story_content_orders_movements(tmp_path: Path) -> None:
    loaded = load_story_content(write_story(tmp_path))

    route = loaded.definition.routes[0]
    beat = route.beats[0]

    assert loaded.definition.entry_route == "principal"
    assert [movement.order for movement in beat.movements] == [1, 2]


def test_rejects_missing_entry_route(tmp_path: Path) -> None:
    invalid = VALID_STORY.replace("entry_route: principal", "entry_route: missing")

    with pytest.raises(StoryContentError):
        load_story_content(write_story(tmp_path, invalid))


def test_rejects_duplicate_movement_order(tmp_path: Path) -> None:
    invalid = VALID_STORY.replace("order: 2", "order: 1")

    with pytest.raises(StoryContentError):
        load_story_content(write_story(tmp_path, invalid))
