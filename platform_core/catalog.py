from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from packages.loader import discover_packages
from packages.models import InstalledStoryPackage
from platform_core.models import AccessStatus, ProgressStatus, StoryCard


INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent.parent / "installed_stories"


def _format_brl(price_cents: int) -> str:
    value = price_cents / 100
    formatted = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


def _cover_url(package_root: Path, cover: str) -> str:
    """Converte uma capa local do pacote em URL utilizável pelo navegador."""
    value = str(cover or "").strip()
    if not value:
        return ""

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https", "data"}:
        return value

    root = package_root.resolve()
    target = (root / value).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return ""

    if not target.is_file():
        return ""

    mime_type, _ = mimetypes.guess_type(target.name)
    if not mime_type or not mime_type.startswith("image/"):
        return ""

    encoded = base64.b64encode(target.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def cover_file_for_package(
    package_id: str,
    *,
    root: Path = INSTALLED_STORIES_ROOT,
) -> Path | None:
    """Resolve a capa declarada sem permitir acesso fora do pacote instalado."""

    packages, _errors = discover_packages(root)
    package = next(
        (item for item in packages if item.manifest.package_id == package_id),
        None,
    )
    if package is None:
        return None
    value = str(package.manifest.card.cover or "").strip()
    if not value or urlparse(value).scheme:
        return None
    package_root = package.root.resolve()
    target = (package_root / value).resolve()
    try:
        target.relative_to(package_root)
    except ValueError:
        return None
    mime_type, _encoding = mimetypes.guess_type(target.name)
    if not target.is_file() or not mime_type or not mime_type.startswith("image/"):
        return None
    return target


def package_to_story_card(package: InstalledStoryPackage) -> StoryCard:
    manifest = package.manifest
    card = manifest.card
    commerce = manifest.commerce
    profile = card.character_profile
    is_free = commerce.access == "free"

    return StoryCard(
        package_id=manifest.package_id,
        title=card.title,
        subtitle=card.subtitle,
        description=card.description,
        genres=card.genres,
        access_status=AccessStatus.FREE if is_free else AccessStatus.LOCKED,
        progress_status=ProgressStatus.NOT_STARTED,
        price_label="" if is_free else _format_brl(commerce.price_cents),
        chapter_label=card.chapter_label,
        cover_url=_cover_url(package.root, card.cover),
        is_tasting=is_free,
        profile_name=profile.name if profile else card.title,
        profile_identity=profile.identity if profile else card.description,
        profile_personality=profile.personality if profile else "",
        profile_intention=profile.intention if profile else "",
        replay_requires_purchase=commerce.replay_policy == "new_purchase",
    )


def load_catalog(root: Path = INSTALLED_STORIES_ROOT) -> tuple[list[StoryCard], list[str]]:
    packages, errors = discover_packages(root)
    cards = [package_to_story_card(package) for package in packages]
    return cards, errors


def load_demo_catalog() -> list[StoryCard]:
    """Compatibilidade temporária com a interface da PR #1."""
    cards, _ = load_catalog()
    return cards
