from __future__ import annotations

from pathlib import Path

from packages.loader import discover_packages
from packages.models import InstalledStoryPackage
from platform_core.models import AccessStatus, ProgressStatus, StoryCard


INSTALLED_STORIES_ROOT = Path(__file__).resolve().parent.parent / "installed_stories"


def _format_brl(price_cents: int) -> str:
    value = price_cents / 100
    formatted = f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {formatted}"


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
        cover_url=str(package.root / card.cover) if card.cover else "",
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
