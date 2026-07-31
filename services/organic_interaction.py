from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True, slots=True)
class OrganicSignal:
    kind: str
    facts: dict[str, str]
    instruction: str
    fallback: str


_NAME_PATTERNS = (
    re.compile(r"\bme\s+chamo\s+([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,30})", re.IGNORECASE),
    re.compile(r"\bmeu\s+nome\s+[ée]\s+([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,30})", re.IGNORECASE),
)


def detect_organic_signal(user_text: str, known_facts: dict[str, str] | None = None) -> OrganicSignal | None:
    """Detecta contribuições que merecem resposta antes do próximo beat."""

    text = " ".join(user_text.strip().split())
    if not text:
        return None

    facts = dict(known_facts or {})
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = _clean_name(match.group(1))
            if name:
                facts["user_name"] = name
                return OrganicSignal(
                    kind="fact_acknowledgement",
                    facts=facts,
                    instruction=(
                        f"Reconheça claramente que o nome do usuário é {name}. "
                        "Use o nome na resposta e, se ele perguntou o seu nome, diga que você se chama Mary. "
                        "Responda ao tom de vizinhança ou brincadeira antes de retomar o roteiro."
                    ),
                    fallback=f"{name}... prazer. Agora não esqueço mais, rsrsrs. Eu sou a Mary.",
                )

    known_name = str(facts.get("user_name", "")).strip()
    lowered = text.casefold()
    if known_name and any(term in lowered for term in ("soletra", "soletrar", "como se escreve", "letra por letra")):
        spelling = "-".join(list(known_name.upper()))
        return OrganicSignal(
            kind="related_challenge",
            facts=facts,
            instruction=(
                f"Aceite o desafio com humor e soletre o nome corretamente: {spelling}. "
                "Depois, retome de modo natural a intenção do beat, sem parecer que mudou de assunto abruptamente."
            ),
            fallback=f"Ah, então é assim? Um desafio! {known_name}... {spelling}. Acertei? rsrsrsrs.",
        )

    if "?" in text and len(text.split()) >= 3:
        return OrganicSignal(
            kind="direct_question",
            facts=facts,
            instruction=(
                "Responda primeiro à pergunta direta do usuário de forma curta e natural. "
                "Não ignore a pergunta para recitar a próxima fala obrigatória."
            ),
            fallback="Espera... deixa eu te responder direito antes de continuar.",
        )

    return None


def render_facts(facts: dict[str, Any]) -> str:
    items = [f"{key}={value}" for key, value in facts.items() if str(value).strip()]
    return ", ".join(items) if items else "nenhum fato pessoal confirmado"


def _clean_name(value: str) -> str:
    cleaned = value.strip(" .,!?:;\"'()[]{}")
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:].lower()
