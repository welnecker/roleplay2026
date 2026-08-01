from roleplay.engine import StoryEngine
from roleplay.models import Movement, StoryDefinition, StoryState
from roleplay.validator import enforce_movement


def _engine() -> tuple[StoryEngine, Movement]:
    movement = Movement(
        order=1,
        route="principal",
        beat="linha_001",
        kind="movimento",
        content="Fala editorial.",
        requires="consent",
    )
    story = StoryDefinition(
        story_id="teste",
        title="Teste",
        sequence=(("principal", "linha_001"),),
        movements=(movement,),
    )
    return StoryEngine(story), movement


def test_stay_mantem_a_mesma_linha_sem_expor_marcador() -> None:
    engine, movement = _engine()
    state = StoryState()

    visible, fallback = enforce_movement(
        "[[ACTION:STAY]]\nVocê consegue me responder primeiro?",
        movement,
    )
    updated = engine.consume(state, movement)

    assert visible == "Você consegue me responder primeiro?"
    assert fallback is False
    assert updated.step_index == 0
    assert updated.consumed_orders == []
    assert updated.finished is False


def test_advance_consume_a_linha() -> None:
    engine, movement = _engine()
    state = StoryState()

    visible, _fallback = enforce_movement(
        "[[ACTION:ADVANCE]]\nTudo bem, vamos.",
        movement,
    )
    updated = engine.consume(state, movement)

    assert visible == "Tudo bem, vamos."
    assert updated.consumed_orders == [1]
    assert updated.finished is True


def test_negativa_encerra_sem_consumir_a_proxima_linha() -> None:
    engine, movement = _engine()
    state = StoryState()

    visible, _fallback = enforce_movement(
        "[[ACTION:END_NEGATIVE]]\nNão precisava falar assim. Acabou aqui.",
        movement,
    )
    updated = engine.consume(state, movement)

    assert visible.endswith("Acabou aqui.")
    assert updated.consumed_orders == []
    assert updated.finished is True
