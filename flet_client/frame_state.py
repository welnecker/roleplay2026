from __future__ import annotations

from dataclasses import dataclass

from roleplay_shared.novel_frame_reveal import frame_sections


@dataclass(frozen=True, slots=True)
class VisualEntry:
    kind: str
    actor: str
    visible_name: str
    body: str
    impact_balloon: bool = False


@dataclass(frozen=True, slots=True)
class VisualFrame:
    frame_id: str
    description: str
    entries: tuple[VisualEntry, ...]


def _actor_and_name(header: str) -> tuple[str, str]:
    argument = header.split(maxsplit=1)[1].strip() if " " in header else ""
    actor, separator, visible_name = argument.partition("|")
    return actor.strip(), visible_name.strip() if separator else ""


def parse_visual_frame(content: str) -> VisualFrame:
    """Converte a saída canônica do runtime em um modelo neutro de frontend."""

    current_id = ""
    description = ""
    entries: list[VisualEntry] = []
    for header, body in frame_sections(content):
        normalized = header.strip()
        upper = normalized.upper()
        if upper.startswith("QUADRO "):
            current_id = normalized.split(maxsplit=1)[1].strip()
        elif upper in {"DESCRIÇÃO", "DESCRICAO"}:
            description = body.strip()
        elif upper.startswith("FALA ") or upper.startswith("PENSAMENTO "):
            kind = "pensamento" if upper.startswith("PENSAMENTO ") else "fala"
            actor, visible_name = _actor_and_name(normalized)
            if body.strip():
                entries.append(
                    VisualEntry(
                        kind=kind,
                        actor=actor,
                        visible_name=visible_name,
                        body=body.strip(),
                        # A diretiva vem do roteiro como ``mary_balao`` e o
                        # contrato do runtime a preserva no actor da saída.
                        # O nome visível continua sendo somente "Mary".
                        impact_balloon=(
                            kind == "fala"
                            and actor.casefold().endswith("_balao")
                        ),
                    )
                )

    if not current_id:
        raise ValueError("Conteúdo não contém um [QUADRO id] válido.")
    return VisualFrame(
        frame_id=current_id,
        description=description,
        entries=tuple(entries),
    )


@dataclass(slots=True)
class FrameRevealController:
    frame: VisualFrame
    revealed_entries: int = 0

    def __post_init__(self) -> None:
        if self.frame.entries and self.revealed_entries <= 0:
            self.revealed_entries = 1
        self.revealed_entries = min(
            max(0, int(self.revealed_entries)),
            len(self.frame.entries),
        )

    @property
    def visible_entries(self) -> tuple[VisualEntry, ...]:
        return self.frame.entries[: self.revealed_entries]

    @property
    def all_entries_visible(self) -> bool:
        return self.revealed_entries >= len(self.frame.entries)

    def advance(self) -> bool:
        """Revela uma entry; retorna True somente quando o quadro já terminou."""

        if self.all_entries_visible:
            return True
        self.revealed_entries += 1
        return False
