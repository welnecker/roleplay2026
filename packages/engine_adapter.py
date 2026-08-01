from __future__ import annotations

from packages.story_content import StoryDefinition as PackageStoryDefinition
from roleplay.models import Movement, StoryDefinition


class StoryEngineAdapterError(ValueError):
    """Raised when declarative package content cannot feed the engine safely."""


def adapt_story_definition(source: PackageStoryDefinition) -> StoryDefinition:
    """Convert validated package YAML into the deterministic engine model."""

    sequence: list[tuple[str, str]] = []
    movements: list[Movement] = []
    seen_orders: set[int] = set()

    for route in source.routes:
        for beat in route.beats:
            sequence.append((route.id, beat.id))
            for item in beat.movements:
                if item.order in seen_orders:
                    raise StoryEngineAdapterError(
                        f"movement order must be globally unique: {item.order}"
                    )
                seen_orders.add(item.order)
                movements.append(
                    Movement(
                        order=item.order,
                        route=route.id,
                        beat=beat.id,
                        kind="movimento",
                        content=item.content,
                        thought=item.thought,
                        requires=item.requires,
                        scene=item.scene,
                    )
                )

    if not sequence:
        raise StoryEngineAdapterError("story must contain at least one route and beat")

    entry_index = next(
        (
            index
            for index, (route_id, _beat_id) in enumerate(sequence)
            if route_id == source.entry_route
        ),
        None,
    )
    if entry_index is None:
        raise StoryEngineAdapterError("entry route was not found in story sequence")

    ordered_sequence = tuple(sequence[entry_index:] + sequence[:entry_index])

    return StoryDefinition(
        story_id=source.story_id,
        title=source.title,
        sequence=ordered_sequence,
        movements=tuple(sorted(movements, key=lambda movement: movement.order)),
    )
