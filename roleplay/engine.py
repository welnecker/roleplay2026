from __future__ import annotations

from .interaction_control import consume_interaction_action
from .models import Movement, StoryDefinition, StoryState


class StoryEngine:
    """Motor linear: o roteiro fornece a linha; o modelo decide avançar, esperar ou encerrar."""

    def __init__(self, story: StoryDefinition) -> None:
        self.story = story

    def current_step(self, state: StoryState) -> tuple[str, str] | None:
        if state.finished or state.step_index >= len(self.story.sequence):
            return None
        return self.story.sequence[state.step_index]

    def movements_for_current_step(self, state: StoryState) -> tuple[Movement, ...]:
        step = self.current_step(state)
        if step is None:
            return ()
        route, beat = step
        consumed = set(state.consumed_orders)
        return tuple(
            sorted(
                (
                    movement
                    for movement in self.story.movements
                    if movement.route == route
                    and movement.beat == beat
                    and movement.kind.casefold() != "regra"
                    and movement.order not in consumed
                ),
                key=lambda movement: movement.order,
            )
        )

    def next_movement(self, state: StoryState) -> Movement | None:
        self._advance_empty_steps(state)
        remaining = self.movements_for_current_step(state)
        return remaining[0] if remaining else None

    def consume(self, state: StoryState, movement: Movement) -> StoryState:
        expected = self.next_movement(state)
        if expected is None:
            raise RuntimeError("A história não possui movimento pendente.")
        if movement.order != expected.order:
            raise ValueError(
                f"Movimento fora de ordem: esperado={expected.order}, recebido={movement.order}."
            )

        action = consume_interaction_action()
        updated = state.copy()

        if action == "stay":
            return updated

        if action in {"end_negative", "end_hallucination", "end_refusal"}:
            updated.finished = True
            return updated

        updated.consumed_orders.append(movement.order)
        self._advance_empty_steps(updated)
        return updated

    def _advance_empty_steps(self, state: StoryState) -> None:
        while not state.finished:
            if state.step_index >= len(self.story.sequence):
                state.finished = True
                return
            if self.movements_for_current_step(state):
                return
            state.step_index += 1
