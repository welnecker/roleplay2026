from __future__ import annotations

import re
import unicodedata

_OUTPUT_MARKER = re.compile(r"^\s*\[([^\]]+)\]\s*$", re.MULTILINE)
_INLINE_MARKER = re.compile(
    r"(?mi)^\s*(\[(?:QUADRO\s+[^\]]+|DESCRI(?:Ç|C)ÃO|FALA\s+[^\]]+|PENSAMENTO\s+[^\]]+|/QUADRO)\])\s+([^\r\n]+)$"
)


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(char for char in text if not unicodedata.combining(char)).casefold().strip()


def normalize_frame_markers(content: str) -> str:
    """Normaliza tags que o modelo eventualmente devolve com texto na mesma linha."""

    value = str(content or "").strip()
    previous = None
    while value != previous:
        previous = value
        value = _INLINE_MARKER.sub(lambda match: f"{match.group(1)}\n{match.group(2).strip()}", value)
    return value


def is_frame_content(content: str) -> bool:
    value = normalize_frame_markers(content)
    return value.startswith("[QUADRO ") and "[/QUADRO]" in value


def _sections(content: str) -> list[tuple[str, str]]:
    value = normalize_frame_markers(content)
    if not is_frame_content(value):
        return []
    matches = list(_OUTPUT_MARKER.finditer(value))
    result: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        header = match.group(1).strip()
        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        body = value[body_start:body_end].strip()
        result.append((header, body))
    return result


def frame_entry_count(content: str) -> int:
    count = 0
    for header, _body in _sections(content):
        first = _plain(header.split(maxsplit=1)[0] if header else "")
        if first in {"fala", "pensamento"}:
            count += 1
    return count


def frame_id(content: str) -> str:
    for header, _body in _sections(content):
        if header.startswith("QUADRO "):
            return header[len("QUADRO "):].strip()
    return ""


def reveal_frame_content(content: str, revealed_entries: int) -> str:
    """Mantém DESCRIÇÃO sempre visível e revela N falas/pensamentos na ordem gerada."""

    sections = _sections(content)
    if not sections:
        return str(content or "")

    limit = max(0, int(revealed_entries or 0))
    visible: list[tuple[str, str]] = []
    entries_seen = 0
    closing = False

    for header, body in sections:
        if header.startswith("QUADRO "):
            visible.append((header, body))
            continue
        if header == "/QUADRO":
            closing = True
            continue

        first = _plain(header.split(maxsplit=1)[0] if header else "")
        if first == "descricao":
            visible.append((header, body))
            continue
        if first in {"fala", "pensamento"}:
            if entries_seen < limit:
                visible.append((header, body))
            entries_seen += 1
            continue

    output: list[str] = []
    for header, body in visible:
        output.append(f"[{header}]")
        if body:
            output.append(body)
    if closing:
        output.append("[/QUADRO]")
    return "\n".join(output).strip()


def reveal_complete(content: str, revealed_entries: int) -> bool:
    return int(revealed_entries or 0) >= frame_entry_count(content)


__all__ = [
    "frame_entry_count",
    "frame_id",
    "is_frame_content",
    "normalize_frame_markers",
    "reveal_complete",
    "reveal_frame_content",
]
