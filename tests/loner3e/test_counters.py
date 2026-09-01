import pytest
from core_test_support import initialized
from pydantic import ValidationError

from aidm.core.entities import EntityId
from aidm.engines.core import Counter
from aidm.engines.loner3e.tools import adjust
from aidm.engines.loner3e.world import Loner3eGame, LonerCharacter

KAEL = LonerCharacter(id=EntityId("kael"), name="Kael", brief="", known=True)


def _state() -> Loner3eGame:
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
    (changed,) = adjust(state.payload.world.player_id, KAEL, "stress", counter, 99, "the strain")
    assert (changed.card, counter.current) == ("Kael: Stress +5 -> 5/5", 5)
    assert adjust(state.payload.world.player_id, KAEL, "stress", counter, 99, "the strain") == []

    counter.current = 0
    (own,) = adjust(
        state.payload.world.player_id,
        state.payload.world.player,
        "stress",
        counter,
        1,
        "the strain",
    )
    assert own.card == "Stress +1 -> 1/5"
