from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class StoryContentError(RuntimeError):
    """Raised when a story entrypoint cannot be loaded safely."""


class MovementDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: int = Field(ge=1)
    content: str = Field(min_length=1)
    thought: str = ""
    scene: str = ""
    requires: Literal["", "answer", "plaza_confirmation", "consent", "name", "phone", "call_permission"] = ""

    @field_validator("content", "thought", "scene")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class BeatDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    movements: tuple[MovementDefinition, ...] = Field(min_length=1)

    @field_validator("movements")
    @classmethod
    def validate_orders(
        cls,
        value: tuple[MovementDefinition, ...],
    ) -> tuple[MovementDefinition, ...]:
        orders = [movement.order for movement in value]
        if len(orders) != len(set(orders)):
            raise ValueError("movement orders must be unique inside a beat")
        return tuple(sorted(value, key=lambda movement: movement.order))


class RouteDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    beats: tuple[BeatDefinition, ...] = Field(min_length=1)

    @field_validator("beats")
    @classmethod
    def validate_beat_ids(
        cls,
        value: tuple[BeatDefinition, ...],
    ) -> tuple[BeatDefinition, ...]:
        identifiers = [beat.id for beat in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("beat ids must be unique inside a route")
        return value


class StoryDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    story_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    entry_route: str = Field(min_length=1)
    routes: tuple[RouteDefinition, ...] = Field(min_length=1)

    @field_validator("routes")
    @classmethod
    def validate_route_ids(
        cls,
        value: tuple[RouteDefinition, ...],
    ) -> tuple[RouteDefinition, ...]:
        identifiers = [route.id for route in value]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("route ids must be unique")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.entry_route not in {route.id for route in self.routes}:
            raise ValueError("entry_route must reference an existing route")


@dataclass(frozen=True, slots=True)
class LoadedStoryContent:
    definition: StoryDefinition
    source: Path


def load_story_content(entrypoint: Path) -> LoadedStoryContent:
    source = entrypoint.resolve()
    if not source.is_file():
        raise StoryContentError(f"Story entrypoint not found: {source}")

    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise StoryContentError(f"Cannot read story entrypoint {source}: {exc}") from exc

    if not isinstance(raw, dict):
        raise StoryContentError(f"Story entrypoint must contain a YAML object: {source}")

    try:
        definition = StoryDefinition.model_validate(raw)
    except ValidationError as exc:
        raise StoryContentError(f"Invalid story entrypoint {source}: {exc}") from exc

    return LoadedStoryContent(definition=definition, source=source)
