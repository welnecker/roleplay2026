from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping


def _frozen_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


@dataclass(frozen=True, slots=True)
class TransitionCondition:
    intent: str = ""
    engagement: str = ""
    facts: Mapping[str, str] = field(default_factory=dict)
    relationship: Mapping[str, int] = field(default_factory=dict)
    always: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts", _frozen_mapping(self.facts))
        object.__setattr__(self, "relationship", _frozen_mapping(self.relationship))


@dataclass(frozen=True, slots=True)
class TransitionEffects:
    facts: Mapping[str, str] = field(default_factory=dict)
    relationship: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "facts", _frozen_mapping(self.facts))
        object.__setattr__(self, "relationship", _frozen_mapping(self.relationship))


@dataclass(frozen=True, slots=True)
class NarrativeEffect:
    status: str = ""
    required_outcomes: tuple[str, ...] = ()
    forbidden_outcomes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransitionRule:
    transition_id: str
    condition: TransitionCondition
    next_beat_id: str = ""
    stay: bool = False
    priority: int = 0
    effects: TransitionEffects = field(default_factory=TransitionEffects)
    narrative_effect: NarrativeEffect = field(default_factory=NarrativeEffect)
    prompt: str = ""
    fallback: str = ""

    def __post_init__(self) -> None:
        if not self.transition_id.strip():
            raise ValueError("Toda transição deve possuir id.")
        if self.stay == bool(self.next_beat_id.strip()):
            raise ValueError(
                "A transição deve declarar exatamente um destino: next ou stay."
            )


@dataclass(frozen=True, slots=True)
class TransitionDecision:
    transition_id: str
    target_beat_id: str
    stay: bool
    effects: TransitionEffects
    narrative_effect: NarrativeEffect = field(default_factory=NarrativeEffect)
    prompt: str = ""
    fallback: str = ""
