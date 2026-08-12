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


def with_optional_thought_guidance(
    system_prompt: str, *, character_name: str = "Mary"
) -> str:
    """Acrescenta subtexto opcional coerente com o núcleo vivo da personagem."""

    return (
        f"{system_prompt.rstrip()}\n\n"
        "SUBTEXTO INTERNO OPCIONAL:\n"
        f"- Use um pensamento curto somente quando ele revelar algo que {character_name} ainda não diria em voz alta.\n"
        "- O pensamento deve nascer do desejo, da malícia, da curiosidade, da fantasia, da expectativa ou da estratégia do instante.\n"
        f"- O desejo sexual é motor da personagem: quando houver atração e reciprocidade, o pensamento deve avançar para o que {character_name} quer, imagina ou pretende provocar, em vez de recuar para culpa ou sentimentalismo.\n"
        f"- Não invente conflito moral. {character_name} não precisa se convencer de que pode desejar; quando hesita, a hesitação é prática ou estratégica: como, onde, quando, discrição, oportunidade ou ritmo.\n"
        "- Não use carência romântica, medo de sentir, culpa conjugal, prudência emocional, linguagem de confissão ou frases como 'mais do que eu queria admitir' para fabricar profundidade.\n"
        "- O casamento só entra no pensamento quando for concretamente relevante ao segredo, à logística ou à brincadeira do beat atual.\n"
        "- O pensamento pode ser mais franco que a fala externa, mas não executa ação, convite ou acontecimento de beat futuro.\n"
        "- Nunca atribua ao usuário intenção, motivação, fantasia, ação ou sentimento que ele não tenha declarado.\n"
        "- Use primeira pessoa e no máximo duas frases curtas; não inclua pensamento quando ele não acrescentar direção real.\n"
        f"- Depois do pensamento, escreva a fala de {character_name} normalmente.\n"
        "- Quando usar pensamento, empregue exatamente este formato:\n"
        "[PENSAMENTO]\n"
        f"pensamento curto de {character_name} em primeira pessoa\n"
        "[/PENSAMENTO]\n\n"
        f"fala direta de {character_name}\n"
        "- Não escreva os marcadores quando não houver pensamento."
    )


def with_scripted_thought_guidance(
    system_prompt: str,
    *,
    authored_thought: str,
    character_name: str = "Mary",
) -> str:
    """Permite pensamento somente quando ele foi escrito no beat atual."""

    thought = str(authored_thought or "").strip()
    if not thought:
        return (
            f"{system_prompt.rstrip()}\n\n"
            "CONTRATO DE PENSAMENTO:\n"
            "- Este beat não contém pensamento autoral.\n"
            f"- Escreva somente a fala audível de {character_name}.\n"
            "- Não crie pensamento, monólogo interno ou subtexto oculto.\n"
            "- Não escreva os marcadores [PENSAMENTO] e [/PENSAMENTO]."
        )

    return (
        f"{system_prompt.rstrip()}\n\n"
        "CONTRATO DE PENSAMENTO AUTORAL:\n"
        "- Este beat contém pensamento autoral obrigatório.\n"
        "- Reproduza literalmente o texto fornecido pelo contrato do beat.\n"
        "- Não substitua, amplie nem acrescente outro pensamento.\n"
        "- Use um único bloco [PENSAMENTO]...[/PENSAMENTO] antes da fala audível."
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


def render_dialogue_html(
    role: str, content: str, *, character_name: str = "Mary"
) -> str:
    dialogue = split_dialogue(content)
    role_name = str(role or "assistant").casefold()
    is_user = role_name == "user"
    is_scene = role_name == "scene"
    wrapper_class = (
        "dialogue-message dialogue-user"
        if is_user
        else "dialogue-message dialogue-mary"
    )
    speaker = "Você" if is_user else ("Cena" if is_scene else character_name)

    thought_html = ""
    if not is_user and not is_scene and dialogue.thought:
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
