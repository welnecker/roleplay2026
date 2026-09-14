from __future__ import annotations

from flet_api.runs import FletRunService


def test_r2_image_does_not_require_local_copy(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ENTRECENAS_MEDIA_URL", "https://media.example.com")

    url = FletRunService._narrative_image_url(
        "roleplay2026.degustacao",
        tmp_path,
        "degustacao1.webp",
    )

    assert url == (
        "https://media.example.com/stories/"
        "roleplay2026.degustacao/scenes/degustacao1.webp"
    )


def test_missing_local_image_without_r2_stays_empty(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ENTRECENAS_MEDIA_URL", raising=False)

    url = FletRunService._narrative_image_url(
        "roleplay2026.degustacao",
        tmp_path,
        "degustacao1.webp",
    )

    assert url == ""
