from pathlib import Path

from flet_api.public_media import public_story_media_url


def test_public_story_media_is_disabled_without_base_url(monkeypatch) -> None:
    monkeypatch.delenv("ENTRECENAS_MEDIA_URL", raising=False)

    assert public_story_media_url("story.free", "cover", "capa.webp") == ""


def test_public_story_media_builds_stable_r2_url(monkeypatch) -> None:
    monkeypatch.setenv("ENTRECENAS_MEDIA_URL", "https://midia.example.com/")

    url = public_story_media_url(
        "roleplay2026.história livre",
        "scenes",
        Path("/tmp/cena 01.webp"),
    )

    assert url == (
        "https://midia.example.com/stories/roleplay2026.hist%C3%B3ria%20livre/"
        "scenes/cena%2001.webp"
    )
