from __future__ import annotations

import re
from typing import Any, Mapping

from packages.models import PackageCastCustomization, StoryPackageManifest


MAX_CAST_NAME_LENGTH = 40
_NAME_PATTERN = re.compile(r"^[^\r\n\t<>]+$")
_GENDER_TO_STORY = {
    "masculine": "Como homem",
    "feminine": "Como mulher",
    "neutral": "De forma neutra",
}


def active_cast(manifest: StoryPackageManifest) -> PackageCastCustomization | None:
    config = manifest.cast_customization
    return config if config.enabled and config.members else None


def default_cast_names(manifest: StoryPackageManifest) -> dict[str, str]:
    config = active_cast(manifest)
    if config is None:
        return {}
    return {member.actor_id: member.default_name for member in config.members}


def normalize_cast_names(
    manifest: StoryPackageManifest,
    supplied: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Validate a complete per-run cast, filling omitted roles with defaults."""

    config = active_cast(manifest)
    if config is None:
        if supplied:
            raise ValueError("Esta história não oferece personalização de personagens.")
        return {}

    requested = {
        str(actor_id or "").strip().casefold(): str(name or "").strip()
        for actor_id, name in dict(supplied or {}).items()
    }
    allowed = {member.actor_id for member in config.members}
    unknown = sorted(set(requested) - allowed)
    if unknown:
        raise ValueError("Personagem inválido para esta história.")

    result: dict[str, str] = {}
    for member in config.members:
        name = requested.get(member.actor_id, member.default_name).strip()
        if not name:
            raise ValueError(f"Informe um nome para {member.label.lower()}.")
        if len(name) > MAX_CAST_NAME_LENGTH:
            raise ValueError(
                f"O nome de {member.label.lower()} deve ter no máximo "
                f"{MAX_CAST_NAME_LENGTH} caracteres."
            )
        if not _NAME_PATTERN.fullmatch(name):
            raise ValueError(f"O nome de {member.label.lower()} contém caracteres inválidos.")
        result[member.actor_id] = name

    folded = [name.casefold() for name in result.values()]
    if len(folded) != len(set(folded)):
        raise ValueError("Use um nome diferente para cada personagem.")
    return result


def cast_profile(
    manifest: StoryPackageManifest,
    supplied: Mapping[str, Any] | None,
) -> dict[str, object]:
    names = normalize_cast_names(manifest, supplied)
    config = active_cast(manifest)
    if config is None:
        raise ValueError("Esta história não oferece personalização de personagens.")

    by_actor = {member.actor_id: member for member in config.members}
    protagonist_id = "usuario" if "usuario" in names else config.members[0].actor_id
    protagonist = names[protagonist_id]
    gender = _GENDER_TO_STORY[by_actor[protagonist_id].gender]
    return {
        "preferred_name": protagonist,
        "name": protagonist,
        "user_name": protagonist,
        "story_gender": gender,
        "identity_mode": "cast",
        "cast_names": names,
        "cast_default_names": default_cast_names(manifest),
        "completed": True,
        "stage": 3,
    }


def enrich_cast_profile(
    manifest: StoryPackageManifest,
    profile: Mapping[str, Any],
) -> dict[str, object]:
    result = dict(profile)
    if str(result.get("identity_mode", "") or "") != "cast":
        return result
    names = normalize_cast_names(manifest, result.get("cast_names") or {})
    refreshed = cast_profile(manifest, names)
    # Preserve future optional immersive fields while rebuilding authoritative cast facts.
    result.update(refreshed)
    return result


__all__ = [
    "MAX_CAST_NAME_LENGTH",
    "active_cast",
    "cast_profile",
    "default_cast_names",
    "enrich_cast_profile",
    "normalize_cast_names",
]
