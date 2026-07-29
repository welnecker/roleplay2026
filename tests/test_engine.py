from roleplay.engine import StoryEngine
from roleplay.models import StoryState
from stories import CASADA_FRUSTRADA


def test_consumes_orders_sequentially_and_advances_beat_only_when_finished() -> None:
    engine = StoryEngine(CASADA_FRUSTRADA)
    state = StoryState()

    first = engine.next_movement(state)
    assert first is not None
    assert first.order == 10
    assert engine.current_step(state) == ("supermarket_encounter", "injury_check")

    state = engine.consume(state, first)
    second = engine.next_movement(state)
    assert second is not None
    assert second.order == 20
    assert engine.current_step(state) == ("supermarket_encounter", "injury_check")

    state = engine.consume(state, second)
    third = engine.next_movement(state)
    assert third is not None
    assert third.order == 30
    assert engine.current_step(state) == ("supermarket_encounter", "recognize_plaza")

    state = engine.consume(state, third)
    assert state.finished is True
    assert state.consumed_orders == [10, 20, 30]
    assert engine.next_movement(state) is None


def test_rejects_out_of_order_consumption() -> None:
    engine = StoryEngine(CASADA_FRUSTRADA)
    state = StoryState()
    wrong = CASADA_FRUSTRADA.movements[1]

    try:
        engine.consume(state, wrong)
    except ValueError as exc:
        assert "esperado=10" in str(exc)
    else:
        raise AssertionError("O motor aceitou movimento fora de ordem.")
