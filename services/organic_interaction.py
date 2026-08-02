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
_FREE_REACTION_PATTERNS = (
    re.compile(r"\bvoc[eê]\s+(?:é|e|tá|ta|parece|ficou|fica|chupa|fode|goza)\b", re.IGNORECASE),
    re.compile(r"\b(?:tenho medo|tô com medo|estou com medo|é perigoso|e perigoso|não quero morrer|nao quero morrer)\b", re.IGNORECASE),
    re.compile(r"\bmas\b.*\b(?:perigoso|medo|morrer|risco|arriscado)\b", re.IGNORECASE),
    re.compile(r"\b(?:chupa|fode|goza)\b.*\b(?:vadia|vagabunda|safada)\b", re.IGNORECASE),
)


def detect_organic_signal(user_text: str, known_facts: dict[str, str] | None = None) -> OrganicSignal | None:
    """Detecta contribuições que merecem uma resposta exclusiva antes do próximo beat."""

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
                "Não execute a próxima linha canônica nesta mesma resposta."
            ),
            fallback=f"Ah, então é assim? Um desafio! {known_name}... {spelling}. Acertei? rsrsrsrs.",
        )

    # Ressalvas, preocupações e provocações contextuais precisam ser reconhecidas
    # antes da regra genérica de pergunta. Caso contrário, uma frase como
    # "é perigoso... não quero morrer, né?" vira apenas direct_question e não
    # abre a folga orgânica exclusiva.
    if len(text.split()) >= 3 and any(pattern.search(text) for pattern in _FREE_REACTION_PATTERNS):
        return OrganicSignal(
            kind="free_reaction",
            facts=facts,
            instruction=(
                "Reaja livremente ao comentário, preocupação ou provocação do usuário dentro da personalidade, memória e situação atual de Mary. "
                "Esta resposta é uma folga orgânica: não avance o acontecimento, não recite e não parafraseie a próxima linha canônica."
            ),
            fallback="Calma... eu entendi o que você quis dizer. Não vou ignorar isso.",
        )

    if "?" in text and len(text.split()) >= 3:
        return OrganicSignal(
            kind="direct_question",
            facts=facts,
            instruction=(
                "Responda primeiro à pergunta direta do usuário de forma curta e natural. "
                "Depois conecte a resposta ao movimento atual sem ignorar o que ele perguntou."
            ),
            fallback="Espera... deixa eu te responder direito antes de continuar.",
        )

    return None


def render_facts(facts: dict[str, Any]) -> str:
    """Renderiza apenas fatos narrativos; chaves iniciadas por '_' são do runtime."""

    items = [
        f"{key}={value}"
        for key, value in facts.items()
        if not str(key).startswith("_") and str(value).strip()
    ]
    return ", ".join(items) if items else "nenhum fato pessoal confirmado"


def _clean_name(value: str) -> str:
    cleaned = value.strip(" .,!?:;\"'()[]{}")
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:].lower()
