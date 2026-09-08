from __future__ import annotations

from roleplay import openrouter


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": "descrição curta"}}]}


def test_image_analysis_uses_one_private_bounded_request(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs)
        return _Response()

    monkeypatch.setattr(openrouter.requests, "post", fake_post)
    result = openrouter.describe_session_image(
        api_key="secret",
        model="vision-model",
        image_bytes=b"private-image",
        mime_type="image/jpeg",
        prompt="descreva",
        max_tokens=220,
    )
    assert result == "descrição curta"
    assert len(calls) == 1
    payload = calls[0]["json"]
    assert payload["max_tokens"] == 220
    assert payload["temperature"] == 0.1
