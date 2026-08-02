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
    re.compile(r"\bsou\s+(?:o\s+|a\s+)?([A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]{1,30})\b", re.IGNORECASE),
)
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?55[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?\d(?:[\s.-]?\d){7,10}(?!\d)")
_EXCLUSIVE_REACTION_PATTERNS = (
    re.compile(r"\bvoc[eê]\s+(?:é|e)\s+(?:[\wÀ-ÖØ-öø-ÿ'’-]+\s+){0,3}louca\b", re.IGNORECASE),
    re.compile(r"\b(?:tenho medo|tô com medo|estou com medo|é perigoso|e perigoso|não quero morrer|nao quero morrer)\b", re.IGNORECASE),
    re.compile(r"\bmas\b.*\b(?:perigoso|medo|morrer|risco|arriscado)\b", re.IGNORECASE),
    re.compile(r"\b(?:chupa|fode|goza)\b.*\b(?:vadia|vagabunda|safada)\b", re.IGNORECASE),
)
_INTEGRATED_REACTION_PATTERNS = (
    re.compile(r"\bvoc[eê]\s+(?:é|e|tá|ta|parece|ficou|fica|chupa|fode|goza)\b", re.IGNORECASE),
    re.compile(r"\b(?:linda|lindo|gostosa|gostoso|deliciosa|delicioso|tesão|tesao|sexy)\b", re.IGNORECASE),
    re.compile(r"\b(?:corpo|quadril|bunda|seios?|peitos?|xoxota|buceta|pau|rola)\b", re.IGNORECASE),
)


def extract_user_facts(
    user_text: str,
    known_facts: dict[str, str] | None = None,
) -> dict[str, str]:
    """Extrai fatos explícitos sem depender de existir uma reação orgânica."""

    facts = dict(known_facts or {})
    text = " ".join(str(user_text or "").strip().split())
    if not text:
        return facts

    phone = _extract_phone(text)
    if phone:
        facts["user_phone"] = phone

    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        name = _clean_name(match.group(1))
        if name and name.casefold() not in {"homem", "mulher", "cara", "gata", "princesa"}:
            facts["user_name"] = name
            break

    return facts


def detect_organic_signal(user_text: str, known_facts: dict[str, str] | None = None) -> OrganicSignal | None:
    """Classifica a reação; a extração de fatos ocorre independentemente do resultado."""

    text = " ".join(user_text.strip().split())
    if not text:
        return None

    original_facts = dict(known_facts or {})
    facts = extract_user_facts(text, original_facts)
    new_name = str(facts.get("user_name", "")).strip()
    previous_name = str(original_facts.get("user_name", "")).strip()

    if new_name and new_name != previous_name:
        return OrganicSignal(
            kind="fact_acknowledgement",
            facts=facts,
            instruction=(
                f"Reconheça claramente que o nome do usuário é {new_name}. "
                "Use o nome na resposta e, se ele perguntou o seu nome, diga que você se chama Mary. "
                "Responda ao tom de vizinhança ou brincadeira antes de retomar o roteiro."
            ),
            fallback=f"{new_name}... prazer. Agora não esqueço mais, rsrsrs. Eu sou a Mary.",
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

    if len(text.split()) >= 3 and any(pattern.search(text) for pattern in _EXCLUSIVE_REACTION_PATTERNS):
        return OrganicSignal(
            kind="free_reaction",
            facts=facts,
            instruction=(
                "Reaja exclusivamente à preocupação, ressalva ou comentário sensível do usuário. "
                "Não avance o acontecimento, não recite e não parafraseie a próxima linha canônica nesta resposta."
            ),
            fallback="Calma... eu entendi o que você quis dizer. Não vou ignorar isso.",
        )

    if len(text.split()) >= 3 and any(pattern.search(text) for pattern in _INTEGRATED_REACTION_PATTERNS):
        return OrganicSignal(
            kind="integrated_reaction",
            facts=facts,
            instruction=(
                "Responda primeiro ao conteúdo específico do usuário em uma ou duas frases curtas e naturais. "
                "Em seguida, conecte essa reação à linha canônica do movimento atual na mesma mensagem. "
                "A reação e o beat devem formar uma única continuidade. Não abra uma pergunta paralela, "
                "não repita uma provocação já respondida e não antecipe o próximo beat."
            ),
            fallback="Eu ouvi exatamente o que você disse... e isso mexeu comigo.",
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


def _extract_phone(text: str) -> str:
    match = _PHONE_PATTERN.search(str(text or ""))
    if match is None:
        return ""
    digits = re.sub(r"\D", "", match.group(0))
    if digits.startswith("55") and len(digits) > 11:
        digits = digits[2:]
    return digits if 8 <= len(digits) <= 11 else ""


def _clean_name(value: str) -> str:
    cleaned = value.strip(" .,!?:;\"'()[]{}")
    if not cleaned:
        return ""
    return cleaned[:1].upper() + cleaned[1:].lower()
