from __future__ import annotations

from services.editorial_runtime_impl import classify_user_message as base_classify_user_message


_SEXUAL_CONTEXT_TERMS = (
    "chupa", "chupar", "fode", "foder", "goza", "gozar", "gostosa", "gostoso",
    "delícia", "delicia", "tesão", "tesao", "pau", "rola", "xoxota", "buceta",
)
_CONTEXTUAL_INSULT_TERMS = ("vadia", "vagabunda")
_DIRECT_ABUSE_PATTERNS = (
    "você é uma vadia", "voce e uma vadia", "você é vagabunda",
    "voce e vagabunda",
)


def classify_contextual_editorial_message(text: str) -> str:
    """Ajusta hostilidade apenas quando o contexto sexual é claramente consensual."""

    engagement = base_classify_user_message(text)
    if engagement != "hostile":
        return engagement

    value = " ".join(str(text or "").casefold().split())
    if any(pattern in value for pattern in _DIRECT_ABUSE_PATTERNS):
        return engagement

    contextual = any(term in value for term in _CONTEXTUAL_INSULT_TERMS)
    sexual = any(term in value for term in _SEXUAL_CONTEXT_TERMS)
    return "engaged" if contextual and sexual else engagement


__all__ = ["classify_contextual_editorial_message"]
