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


def split_dialogue(content: str) -> PresentedDialogue:
    """Separa pensamento estruturado da fala, preservando mensagens antigas."""

    value = str(content or "").strip()
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


def _paragraphs(value: str) -> str:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", value) if block.strip()]
    if not blocks and value.strip():
        blocks = [value.strip()]
    return "".join(f"<p>{escape(block).replace(chr(10), '<br>')}</p>" for block in blocks)


def _clean_block(value: str) -> str:
    return re.sub(r"[ \t]+\n", "\n", str(value or "")).strip()
