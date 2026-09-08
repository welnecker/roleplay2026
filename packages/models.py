from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PackageAuthor(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1)
    id: str | None = None


class PackageCharacterProfile(BaseModel):
    """Presentation metadata shown on the back of a story card."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    identity: str = ""
    personality: str = ""
    intention: str = ""


class PackageCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1)
    subtitle: str = ""
    description: str = ""
    genres: tuple[str, ...] = ()
    chapter_label: str = ""
    cover: str = ""
    character_profile: PackageCharacterProfile | None = None


class PackageCastMember(BaseModel):
    """A stable authored role whose visible name can vary per paid run."""

    model_config = ConfigDict(frozen=True)

    actor_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    default_name: str = Field(min_length=1, max_length=40)
    gender: str = "neutral"

    @field_validator("actor_id")
    @classmethod
    def validate_actor_id(cls, value: str) -> str:
        clean = value.strip().casefold()
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
        if any(character not in allowed for character in clean):
            raise ValueError("cast.actor_id contém caracteres inválidos")
        return clean

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, value: str) -> str:
        clean = value.strip().casefold()
        if clean not in {"masculine", "feminine", "neutral"}:
            raise ValueError("cast.gender deve ser masculine, feminine ou neutral")
        return clean


class PackageCastCustomization(BaseModel):
    """Optional run-scoped cast personalization declared by a story package."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    members: tuple[PackageCastMember, ...] = ()

    @model_validator(mode="after")
    def validate_members(self) -> "PackageCastCustomization":
        if self.enabled and not self.members:
            raise ValueError("cast_customization habilitado exige ao menos um personagem")
        actor_ids = [member.actor_id for member in self.members]
        if len(actor_ids) != len(set(actor_ids)):
            raise ValueError("cast_customization contém actor_id duplicado")
        return self


class PackageCommerce(BaseModel):
    model_config = ConfigDict(frozen=True)

    access: str = "free"
    price_cents: int = 0
    currency: str = "BRL"
    replay_policy: str = "reuse_access"

    @field_validator("access")
    @classmethod
    def validate_access(cls, value: str) -> str:
        clean = value.strip().lower()
        if clean not in {"free", "paid"}:
            raise ValueError("access deve ser 'free' ou 'paid'")
        return clean

    @field_validator("replay_policy")
    @classmethod
    def validate_replay_policy(cls, value: str) -> str:
        clean = value.strip().lower()
        if clean not in {"reuse_access", "new_purchase"}:
            raise ValueError(
                "replay_policy deve ser 'reuse_access' ou 'new_purchase'"
            )
        return clean


class EditorialRuntimeConfig(BaseModel):
    """Arquivos editoriais declarados pelo próprio pacote."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1)
    extensions: tuple[str, ...] = ()


class PackageRuntime(BaseModel):
    """Seleciona o runtime sem acoplar o aplicativo a uma história específica."""

    model_config = ConfigDict(frozen=True)

    kind: str = "simple"
    editorial: EditorialRuntimeConfig | None = None

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        clean = value.strip().lower()
        if clean not in {"simple", "editorial"}:
            raise ValueError("runtime.kind deve ser 'simple' ou 'editorial'")
        return clean

    def model_post_init(self, __context: object) -> None:
        if self.kind == "editorial" and self.editorial is None:
            raise ValueError("runtime editorial exige a configuração editorial")
        if self.kind != "editorial" and self.editorial is not None:
            raise ValueError("runtime.editorial só pode ser usado com kind='editorial'")


class StoryPackageManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    format_version: int = 1
    package_id: str = Field(min_length=3)
    version: str = Field(min_length=1)
    author: PackageAuthor
    entrypoint: str = "story.yaml"
    runtime: PackageRuntime = PackageRuntime()
    card: PackageCard
    cast_customization: PackageCastCustomization = PackageCastCustomization()
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
