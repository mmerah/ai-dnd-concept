import pytest
from core_test_support import initialized
from pydantic import ValidationError

from aidm.core.entities import EntityId
from aidm.engines.core import Counter, counter_fact
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
    state = _state()
    KAEL.luck.current = 0
    (changed,) = counter_fact(
        KAEL, KAEL.luck, 99, "Luck", "the strain", state.payload.world.player.id
    )
    assert (changed.card, KAEL.luck.current) == ("Kael: Luck +6 -> 6/6", 6)
    assert (
        counter_fact(KAEL, KAEL.luck, 99, "Luck", "the strain", state.payload.world.player.id) == []
    )

    player = state.payload.world.player
    player.luck.current = 0
    (own,) = counter_fact(
        player, player.luck, 1, "Luck", "the strain", state.payload.world.player.id
    )
    assert own.card == "Luck +1 -> 1/6"
