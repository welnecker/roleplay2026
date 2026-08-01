from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Movement:
    order: int
    route: str
    beat: str
    kind: str
    content: str
    thought: str = ""
    requires: str = ""
    scene: str = ""
    condition: str = ""


@dataclass(frozen=True, slots=True)
class StoryDefinition:
    story_id: str
    title: str
    sequence: tuple[tuple[str, str], ...]
    movements: tuple[Movement, ...]

    def __post_init__(self) -> None:
        if not self.sequence:
            raise ValueError("A história precisa ter ao menos um passo na sequência.")
        orders = [movement.order for movement in self.movements]
        if len(orders) != len(set(orders)):
            raise ValueError("As ordens dos movimentos devem ser únicas.")


@dataclass(slots=True)
class StoryState:
    step_index: int = 0
    consumed_orders: list[int] = field(default_factory=list)
    finished: bool = False

    def copy(self) -> "StoryState":
        return StoryState(
            step_index=self.step_index,
            consumed_orders=list(self.consumed_orders),
            finished=self.finished,
        )
