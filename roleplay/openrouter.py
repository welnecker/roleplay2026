from __future__ import annotations

import json
from typing import Any

import requests


class OpenRouterError(RuntimeError):
    pass


def _debug_log(label: str, payload: object) -> None:
    """Registra diagnóstico sem incluir a chave da API."""

    try:
        rendered = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError):
        rendered = repr(payload)
    print(f"\n===== OPENROUTER DEBUG · {label} =====\n{rendered}\n", flush=True)


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
    request_payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.35,
    }
    _debug_log("PROMPT ENVIADO", request_payload)

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        content = str(payload["choices"][0]["message"]["content"] or "").strip()
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        _debug_log(
            "ERRO RECEBIDO",
            {
                "error_type": type(exc).__name__,
                "error": str(exc),
                "response_status": getattr(locals().get("response"), "status_code", None),
                "response_text": getattr(locals().get("response"), "text", ""),
            },
        )
        raise OpenRouterError(f"Falha ao gerar resposta no OpenRouter: {exc}") from exc

    _debug_log(
        "RESPOSTA RECEBIDA",
        {
            "model": model,
            "content": content,
            "provider_payload": payload,
        },
    )

    if not content:
        raise OpenRouterError("O OpenRouter retornou uma resposta vazia.")
    return content
