from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PackageAuthor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    id: str | None = None


class PackageCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    subtitle: str = ""
    description: str = ""
    genres: tuple[str, ...] = ()
    chapter_label: str = ""
    cover: str = ""


class PackageCommerce(BaseModel):
    model_config = ConfigDict(frozen=True)

    access: str = "free"
    price_cents: int = 0
    currency: str = "BRL"

    @field_validator("access")
    @classmethod
    def validate_access(cls, value: str) -> str:
        clean = value.strip().lower()
        if clean not in {"free", "paid"}:
            raise ValueError("access deve ser 'free' ou 'paid'")
        return clean


class StoryPackageManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    format_version: int = 1
    package_id: str = Field(min_length=3)
    version: str = Field(min_length=1)
    author: PackageAuthor
    entrypoint: str = "story.yaml"
    card: PackageCard
    commerce: PackageCommerce = PackageCommerce()

    @field_validator("package_id")
    @classmethod
    def validate_package_id(cls, value: str) -> str:
        clean = value.strip().lower()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
        if any(character not in allowed for character in clean):
            raise ValueError("package_id contém caracteres inválidos")
        return clean


class InstalledStoryPackage(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    root: Path
    manifest_path: Path
    manifest: StoryPackageManifest
