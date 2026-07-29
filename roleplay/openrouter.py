from __future__ import annotations

from typing import Any

import requests


class OpenRouterError(RuntimeError):
    pass


def generate_response(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    history: list[dict[str, str]],
    user_text: str,
    timeout_seconds: int = 60,
) -> str:
    if not api_key.strip():
        raise OpenRouterError("OPENROUTER_API_KEY não configurada.")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        *history,
        {"role": "user", "content": user_text},
    ]

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.35,
            },
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        content = str(payload["choices"][0]["message"]["content"] or "").strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise OpenRouterError(f"Falha ao gerar resposta no OpenRouter: {exc}") from exc

    if not content:
        raise OpenRouterError("O OpenRouter retornou uma resposta vazia.")
    return content
