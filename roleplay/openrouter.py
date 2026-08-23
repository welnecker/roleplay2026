from __future__ import annotations

import base64
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
    debug_logging: bool = True,
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
    if debug_logging:
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
        if debug_logging:
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

    if debug_logging:
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


def describe_session_image(
    *,
    api_key: str,
    model: str,
    image_bytes: bytes,
    mime_type: str,
    prompt: str,
    max_tokens: int = 240,
    timeout_seconds: int = 60,
) -> str:
    """Analisa uma imagem uma única vez, sem registrar imagem, prompt ou resposta."""

    if not api_key.strip():
        raise OpenRouterError("OPENROUTER_API_KEY não configurada.")
    if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise OpenRouterError("Formato de imagem não suportado.")
    if not image_bytes:
        raise OpenRouterError("A imagem está vazia.")

    encoded = base64.b64encode(image_bytes).decode("ascii")
    request_payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"},
                    },
                ],
            }
        ],
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
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
        # Não inclua response.text: alguns provedores podem ecoar partes da requisição.
        raise OpenRouterError(f"Falha ao analisar a imagem no OpenRouter: {exc}") from exc
    if not content:
        raise OpenRouterError("O OpenRouter retornou uma descrição vazia.")
    return content
