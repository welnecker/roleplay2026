from __future__ import annotations

from flet_client.main import DEFAULT_FLET_API_URL, configured_api_url


def test_uses_published_api_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ROLEPLAY_FLET_API_URL", raising=False)

    assert configured_api_url() == DEFAULT_FLET_API_URL


def test_environment_can_override_published_api(monkeypatch) -> None:
    monkeypatch.setenv("ROLEPLAY_FLET_API_URL", " https://api.example.test/ ")

    assert configured_api_url() == "https://api.example.test"
