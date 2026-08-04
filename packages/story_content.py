from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class StoryContentError(RuntimeError):
    """Raised when a story entrypoint cannot be loaded safely."""


class SceneImageDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    file: str = Field(min_length=1)
    caption: str = ""
    alt: str = ""
    expanded: bool = False

    @field_validator("file", "caption", "alt")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("file")
    @classmethod
    def validate_relative_file(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("scene image file must be a safe relative path")
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise ValueError("scene image file must use jpg, jpeg, png or webp")
        return value


class MovementDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    order: int = Field(ge=1)
    content: str = Field(min_length=1)
    thought: str = ""
    scene: str = ""
    scene_image: SceneImageDefinition | None = None
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


def _inject_scene_images(raw: dict[str, Any], *, source: Path) -> None:
    sidecar = source.with_name("scene_images.yaml")
    if not sidecar.is_file():
        return

    try:
        scene_images = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise StoryContentError(f"Cannot read scene image map {sidecar}: {exc}") from exc

    if not isinstance(scene_images, dict):
        raise StoryContentError(f"Scene image map must contain a YAML object: {sidecar}")

    package_root = source.parent.resolve()
    declared_beats: set[str] = set()
    for route in raw.get("routes", []):
        if not isinstance(route, dict):
            continue
        for beat in route.get("beats", []):
            if not isinstance(beat, dict):
                continue
            beat_id = str(beat.get("id", "")).strip()
            declared_beats.add(beat_id)
            image_data = scene_images.get(beat_id)
            if image_data is None:
                continue
            movements = beat.get("movements")
            if not isinstance(movements, list) or not movements:
                raise StoryContentError(f"Beat {beat_id} cannot receive a scene image without movements")
            if len(movements) != 1:
                raise StoryContentError(
                    f"Beat {beat_id} has multiple movements; declare scene_image inline instead"
                )
            movements[0]["scene_image"] = image_data

    unknown = sorted(set(scene_images) - declared_beats)
    if unknown:
        raise StoryContentError(f"Scene image map references unknown beats: {', '.join(unknown)}")

    for beat_id, image_data in scene_images.items():
        try:
            parsed = SceneImageDefinition.model_validate(image_data)
        except ValidationError as exc:
            raise StoryContentError(f"Invalid scene image for {beat_id}: {exc}") from exc
        asset_path = (package_root / parsed.file).resolve()
        try:
            asset_path.relative_to(package_root)
        except ValueError as exc:
            raise StoryContentError(f"Scene image escapes package root for {beat_id}") from exc
        if not asset_path.is_file():
            raise StoryContentError(f"Scene image not found for {beat_id}: {parsed.file}")


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

    _inject_scene_images(raw, source=source)

    try:
        definition = StoryDefinition.model_validate(raw)
    except ValidationError as exc:
        raise StoryContentError(f"Invalid story entrypoint {source}: {exc}") from exc

    return LoadedStoryContent(definition=definition, source=source)
