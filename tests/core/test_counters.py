import pytest
from core_test_support import initialized
from pydantic import ValidationError

from aidm.engines.core import adjust, spend
from aidm.state.entities import Counter, Entity, EntityId
from aidm.state.model import Game

KAEL = Entity(id=EntityId("kael"), kind="actor", name="Kael", brief="", known=True)


def _state() -> Game:
    """A counter card drops the name for the played character alone, so it needs the state."""
    _, state = initialized()
    return state


def test_counter_rejects_current_outside_its_bounds_and_clamps_in_both_directions() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Counter(current=-1, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Counter(current=11, maximum=10)

    held = Counter(current=5, maximum=10)
    assert held.clamped(-5) == 0
    assert held.clamped(50) == 10


def test_adjust_clamps_to_the_counters_bounds_and_reports_only_a_real_move() -> None:
    counter = Counter(current=0, maximum=5)

    state = _state()
    (changed,) = adjust(state, KAEL, "stress", counter, 99, "the strain")
    assert changed.event is not None
    assert (changed.event.title, counter.current) == ("Kael: Stress +5 -> 5/5", 5)
    assert adjust(state, KAEL, "stress", counter, 99, "the strain") == []

    counter.current = 0
    (own,) = adjust(state, state.player, "stress", counter, 1, "the strain")
    assert own.event is not None and own.event.title == "Stress +1 -> 1/5"


def test_spend_pays_the_pool_and_refuses_what_it_cannot_cover() -> None:
    counter = Counter(current=5, maximum=5)

    state = _state()
    (spent,) = spend(state, KAEL, "stress", counter, 2)
    assert spent.event is not None
    assert (spent.event.title, counter.current) == ("Kael: Stress -2 -> 3/5", 3)

    with pytest.raises(ValueError, match="cannot be spent"):
        _ = spend(state, KAEL, "stress", counter, 4)
