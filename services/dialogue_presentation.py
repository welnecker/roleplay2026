from __future__ import annotations

from dataclasses import dataclass
from html import escape
import re


THOUGHT_OPEN = "[PENSAMENTO]"
THOUGHT_CLOSE = "[/PENSAMENTO]"
_THOUGHT_PATTERN = re.compile(
    r"^\s*\[PENSAMENTO\]\s*(?P<thought>.*?)\s*\[/PENSAMENTO\]\s*(?P<speech>.*)$",
    flags=re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True, slots=True)
class PresentedDialogue:
    thought: str
    speech: str


def with_optional_thought_guidance(system_prompt: str) -> str:
    """Acrescenta subtexto opcional sem transformar pensamento em beat obrigatório."""

    return (
        f"{system_prompt.rstrip()}\n\n"
        "SUBTEXTO INTERNO OPCIONAL:\n"
        "- Quando houver desejo, expectativa, dúvida, humor, incômodo, medo, ciúme, culpa, "
        "curiosidade ou algo que Mary queira revelar apenas indiretamente, você pode abrir a resposta "
        "com um pensamento curto em primeira pessoa.\n"
        "- Não inclua pensamento em toda resposta. Use somente quando ele acrescentar uma camada emocional real.\n"
        "- O pensamento pode orientar veladamente o usuário sobre o que Mary espera, teme ou deseja, "
        "mas não pode dar uma instrução explícita ao usuário.\n"
        "- O pensamento não descreve ações, postura, rosto, mãos, corpo ou cenário.\n"
        "- Depois do pensamento, escreva a fala de Mary normalmente, em um ou mais parágrafos curtos.\n"
        "- Quando usar pensamento, empregue exatamente este formato:\n"
        "[PENSAMENTO]\n"
        "pensamento curto de Mary em primeira pessoa\n"
        "[/PENSAMENTO]\n\n"
        "fala direta de Mary\n"
        "- Não escreva os marcadores quando não houver pensamento."
    )


def split_dialogue(content: str) -> PresentedDialogue:
    """Separa pensamento estruturado da fala, preservando mensagens antigas."""

    value = _normalize_presented_content(content)
    match = _THOUGHT_PATTERN.match(value)
    if match is None:
        return PresentedDialogue(thought="", speech=value)
    return PresentedDialogue(
        thought=_clean_block(match.group("thought")),
        speech=_clean_block(match.group("speech")),
    )


def has_balanced_thought_markers(content: str) -> bool:
    value = str(content or "")
    opens = value.upper().count(THOUGHT_OPEN)
    closes = value.upper().count(THOUGHT_CLOSE)
    return opens == closes and opens <= 1


def render_dialogue_html(role: str, content: str) -> str:
    dialogue = split_dialogue(content)
    role_name = str(role or "assistant").casefold()
    is_user = role_name == "user"
    wrapper_class = "dialogue-message dialogue-user" if is_user else "dialogue-message dialogue-mary"
    speaker = "Você" if is_user else "Mary"

    thought_html = ""
    if not is_user and dialogue.thought:
        thought_html = (
            '<div class="mary-thought">'
            '<div class="mary-thought-label"><span>✦</span> pensamento</div>'
            f'<div class="mary-thought-copy">{_paragraphs(dialogue.thought)}</div>'
            "</div>"
        )

    speech = dialogue.speech or ("..." if not is_user else "")
    return (
        f'<article class="{wrapper_class}">'
        f'<div class="dialogue-speaker">{speaker}</div>'
        f"{thought_html}"
        f'<div class="dialogue-speech">{_paragraphs(speech)}</div>'
        "</article>"
    )


def _normalize_presented_content(content: str) -> str:
    """Remove wrappers comuns sem alterar o texto narrativo real.

    Respostas do modelo ou valores recuperados da persistência podem chegar entre
    aspas, cercas Markdown ou com BOM. Esses wrappers impediam o marcador de
    pensamento de ocupar o início lógico da mensagem e, portanto, a tarja não era
    renderizada.
    """

    value = str(content or "").replace("\ufeff", "").strip()
    if value.startswith("```") and value.endswith("```"):
        value = re.sub(r"^```(?:text|markdown)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        inner = value[1:-1].strip()
        if THOUGHT_OPEN in inner.upper():
            value = inner
    marker_index = value.upper().find(THOUGHT_OPEN)
    if marker_index > 0 and not value[:marker_index].strip(' \t\r\n"\'`'):
        value = value[marker_index:]
    return value.strip()


def _paragraphs(value: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", value) if block.strip()]
    if not blocks and value.strip():
        blocks = [value.strip()]
    return "".join(f"<p>{escape(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def _clean_block(value: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", str(value or "")).strip()
