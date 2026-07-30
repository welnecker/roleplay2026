from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CreditStatus = Literal["available", "consumed", "revoked"]
RunStatus = Literal["active", "completed", "terminated"]
BeatType = Literal[
    "action",
    "dialogue",
    "action_dialogue",
    "internal",
    "transition",
    "ending",
]


@dataclass(frozen=True, slots=True)
class CharacterProfile:
    character_id: str
    name: str
    age: int
    physical_profile: tuple[str, ...]
    psychological_profile: tuple[str, ...]
    speech_style: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EndingResult:
    run_status: Literal["completed", "terminated"]
    ending_code: str
    return_to_library: bool = True


@dataclass(frozen=True, slots=True)
class BeatDefinition:
    beat_id: str
    block_id: str
    order: int
    type: BeatType
    required_movement: str
    canonical_line: str = ""
    dramatic_direction: str = ""
    next_beat_id: str = ""
    max_questions: int = 1
    max_sentences: int | None = None
    memory_writes: tuple[str, ...] = ()
    allowed_transitions: dict[str, str] = field(default_factory=dict)
    ending: EndingResult | None = None

    def __post_init__(self) -> None:
        if self.order < 1:
            raise ValueError("A ordem do beat deve ser positiva.")
        if self.max_questions < 0:
            raise ValueError("max_questions não pode ser negativo.")
        if self.type == "ending" and self.ending is None:
            raise ValueError("Beat de encerramento precisa declarar ending.")


@dataclass(frozen=True, slots=True)
class BlockDefinition:
    block_id: str
    order: int
    title: str
    entry_beat_id: str
    max_movements_per_response: int = 1
    max_questions_per_response: int = 1
    rules: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NarrativePackage:
    package_id: str
    script_version: str
    title: str
    introduction: str
    character: CharacterProfile
    blocks: tuple[BlockDefinition, ...]
    beats: tuple[BeatDefinition, ...]
    memories: dict[str, str]

    def __post_init__(self) -> None:
        beat_ids = [beat.beat_id for beat in self.beats]
        if len(beat_ids) != len(set(beat_ids)):
            raise ValueError("beat_id duplicado no pacote narrativo.")
        block_ids = {block.block_id for block in self.blocks}
        if any(beat.block_id not in block_ids for beat in self.beats):
            raise ValueError("Todo beat deve pertencer a um bloco existente.")


@dataclass(frozen=True, slots=True)
class RunCredit:
    credit_id: str
    user_id: str
    package_id: str
    payment_id: str
    status: CreditStatus
    run_id: str = ""
    created_at: str = ""
    consumed_at: str = ""


@dataclass(slots=True)
class StoryRun:
    run_id: str
    credit_id: str
    user_id: str
    package_id: str
    script_version: str
    current_block_id: str
    current_beat_id: str
    status: RunStatus = "active"
    ending_code: str = ""
    state_version: int = 1
    permanent_memory_ids: list[str] = field(default_factory=list)
    started_at: str = ""
    ended_at: str = ""
    updated_at: str = ""

    def add_memory(self, memory_id: str) -> None:
        if memory_id and memory_id not in self.permanent_memory_ids:
            self.permanent_memory_ids.append(memory_id)

    def finish(self, result: EndingResult, *, ended_at: str) -> None:
        self.status = result.run_status
        self.ending_code = result.ending_code
        self.ended_at = ended_at
        self.updated_at = ended_at
        self.state_version += 1
