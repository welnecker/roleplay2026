from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping


VALID_INTENTS = frozenset({"accept", "refuse", "postpone", "question", "unclear"})
MIN_SEMANTIC_CONFIDENCE = 0.80


@dataclass(frozen=True, slots=True)
class IntentResolution:
    intent: str
    confidence: float
    evidence: str
    explicit_decision: bool
    source: str

    @classmethod
    def unclear(cls, *, source: str = "semantic_unavailable") -> "IntentResolution":
        return cls(
            intent="unclear",
            confidence=0.0,
            evidence="",
            explicit_decision=False,
            source=source,
        )


def declared_intents(classifiers: Any) -> tuple[str, ...]:
    values: list[str] = []
    if isinstance(classifiers, list):
        for classifier in classifiers:
            if not isinstance(classifier, Mapping):
                continue
            intent = str(classifier.get("intent", "") or "").strip()
            if intent in VALID_INTENTS and intent not in values:
                values.append(intent)
    if "unclear" not in values:
        values.append("unclear")
    return tuple(values)


def _dialogue_anchor(beat: Mapping[str, Any]) -> str:
    for unit in beat.get("units", []) or []:
        if isinstance(unit, Mapping) and unit.get("kind") == "dialogue":
            return str(unit.get("anchor") or unit.get("text") or "").strip()
    return ""


def build_semantic_intent_prompt(
    beat: Mapping[str, Any],
    *,
    intents: tuple[str, ...],
) -> str:
    objective = str(beat.get("objective", "") or "").strip()
    canonical = _dialogue_anchor(beat)
    options = ", ".join(intents)
    return (
        "Você classifica a intenção comunicada pelo usuário em uma história interativa.\n"
        "Interprete linguagem brasileira natural, popular, abreviada, regional, com erros, "
        "reticências, humor e respostas indiretas. Avalie o sentido no contexto, não palavras isoladas.\n"
        "Não invente decisão. Condição, dúvida ou ambiguidade não são aceite definitivo. "
        "Adiamento não é recusa. Pergunta não é aceite.\n"
        "Escolha somente uma das intenções declaradas e responda exclusivamente com JSON válido:\n"
        '{"intent":"...","confidence":0.0,"evidence":"trecho literal curto",'
        '"explicit_decision":false}\n'
        f"INTENÇÕES VÁLIDAS: {options}\n"
        f"MOVIMENTO PENDENTE: {objective or 'não informado'}\n"
        f"REFERÊNCIA DO MOVIMENTO: {canonical or 'não informada'}\n"
        "Use unclear quando não houver evidência suficiente no texto do usuário."
    )


def build_semantic_intent_request(user_text: str) -> str:
    return f"MENSAGEM DO USUÁRIO:\n{str(user_text or '').strip()}"


def parse_semantic_intent(
    raw: str,
    *,
    allowed_intents: tuple[str, ...],
) -> IntentResolution:
    try:
        payload = json.loads(str(raw or "").strip())
    except (TypeError, ValueError, json.JSONDecodeError):
        return IntentResolution.unclear(source="semantic_invalid_json")
    if not isinstance(payload, dict):
        return IntentResolution.unclear(source="semantic_invalid_payload")

    intent = str(payload.get("intent", "") or "").strip()
    if intent not in allowed_intents or intent not in VALID_INTENTS:
        return IntentResolution.unclear(source="semantic_invalid_intent")
    try:
        confidence = float(payload.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    evidence = str(payload.get("evidence", "") or "").strip()
    explicit_decision = bool(payload.get("explicit_decision", False))

    if intent in {"accept", "refuse", "postpone"}:
        if confidence < MIN_SEMANTIC_CONFIDENCE or not explicit_decision or not evidence:
            return IntentResolution.unclear(source="semantic_insufficient_evidence")
    elif intent == "question":
        if confidence < MIN_SEMANTIC_CONFIDENCE or not evidence:
            return IntentResolution.unclear(source="semantic_insufficient_evidence")
    elif confidence < 0.50:
        confidence = 0.50

    return IntentResolution(
        intent=intent,
        confidence=confidence,
        evidence=evidence,
        explicit_decision=explicit_decision,
        source="semantic_model",
    )


def resolve_semantic_intent(
    beat: Mapping[str, Any],
    classifiers: Any,
    user_text: str,
) -> IntentResolution:
    """Usa o modelo somente quando as regras declarativas não resolveram a intenção.

    A dependência de Streamlit/OpenRouter é carregada de forma tardia para manter o
    módulo testável. Falha operacional nunca inventa decisão: retorna ``unclear``.
    """

    intents = declared_intents(classifiers)
    if len(intents) <= 1:
        return IntentResolution.unclear(source="semantic_no_choices")
    try:
        import streamlit as st
        from roleplay.openrouter import OpenRouterError, generate_response

        api_key = str(st.secrets.get("OPENROUTER_API_KEY", "") or "").strip()
        model = str(
            st.secrets.get("OPENROUTER_INTENT_MODEL", "")
            or st.secrets.get("OPENROUTER_MODEL", "")
            or "google/gemini-3-flash-preview"
        ).strip()
        if not api_key:
            return IntentResolution.unclear(source="semantic_not_configured")
        raw = generate_response(
            api_key=api_key,
            model=model,
            system_prompt=build_semantic_intent_prompt(beat, intents=intents),
            history=[],
            user_text=build_semantic_intent_request(user_text),
        )
    except Exception as exc:
        if exc.__class__.__name__ == "OpenRouterError":
            return IntentResolution.unclear(source="semantic_provider_error")
        return IntentResolution.unclear(source="semantic_runtime_error")
    return parse_semantic_intent(raw, allowed_intents=intents)


__all__ = [
    "IntentResolution",
    "build_semantic_intent_prompt",
    "build_semantic_intent_request",
    "declared_intents",
    "parse_semantic_intent",
    "resolve_semantic_intent",
]
