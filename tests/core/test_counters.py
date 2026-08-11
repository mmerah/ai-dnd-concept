import pytest
from pydantic import ValidationError

from aidm.engines.counters import Counter, CounterChange, adjust, spend
from aidm.state.base import Entity, EntityId

KAEL = Entity(id=EntityId("kael"), kind="actor", name="Kael", brief="", known=True)


def test_counter_rejects_current_outside_its_bounds_and_clamps_in_both_directions() -> None:
    with pytest.raises(ValidationError, match="below minimum"):
        Counter(current=-1, minimum=0, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Counter(current=11, minimum=0, maximum=10)

    held = Counter(current=5, minimum=0, maximum=10)
    assert held.clamped(-5) == 0
    assert held.clamped(50) == 10


def test_adjust_clamps_to_the_counters_bounds_and_reports_only_a_real_move() -> None:
    counter = Counter(current=0, maximum=5)

    (changed,) = adjust(KAEL, "stress", counter, 99, "the strain")
    assert (changed.data["delta"], counter.current) == (5, 5)
    assert adjust(KAEL, "stress", counter, 99, "the strain") == []


def test_spend_pays_the_pool_and_refuses_what_it_cannot_cover() -> None:
    counter = Counter(current=5, maximum=5)

    (spent,) = spend(KAEL, "stress", counter, 2, "")
    assert (spent.data["current"], counter.current) == (3, 3)

    with pytest.raises(ValueError, match="cannot go below"):
        _ = spend(KAEL, "stress", counter, 4, "")


def test_counter_change_spend_requires_a_positive_amount() -> None:
    with pytest.raises(ValidationError, match="positive amount"):
        CounterChange(mode="spend", entity_id=EntityId("kael"), counter="stress", amount=-1)
