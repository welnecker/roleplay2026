from __future__ import annotations

import pytest

from packages.engine_adapter import StoryEngineAdapterError, adapt_story_definition
from packages.story_content import StoryDefinition
from roleplay.engine import StoryEngine
from roleplay.models import StoryState


def make_story(*, duplicate_order: bool = False) -> StoryDefinition:
    second_order = 1 if duplicate_order else 2
    return StoryDefinition.model_validate(
        {
            "story_id": "example",
            "title": "Example",
            "entry_route": "main",
            "routes": [
                {
                    "id": "main",
                    "beats": [
                        {
                            "id": "opening",
                            "movements": [
                                {"order": 1, "content": "First movement"},
                            ],
                        },
                        {
                            "id": "next",
                            "movements": [
                                {"order": second_order, "content": "Second movement"},
                            ],
                        },
                    ],
                }
            ],
        }
    )


def test_adapter_builds_engine_story() -> None:
    adapted = adapt_story_definition(make_story())
    engine = StoryEngine(adapted)
    state = StoryState()

    first = engine.next_movement(state)
    assert first is not None
    assert first.order == 1
    assert first.route == "main"
    assert first.beat == "opening"

    state = engine.consume(state, first)
    second = engine.next_movement(state)
    assert second is not None
    assert second.order == 2
    assert second.beat == "next"


def test_adapter_rejects_global_duplicate_orders() -> None:
    with pytest.raises(StoryEngineAdapterError):
        adapt_story_definition(make_story(duplicate_order=True))
