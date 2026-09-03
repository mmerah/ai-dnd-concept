import pytest
from core_test_support import initialized
from pydantic import ValidationError

from aidm.core.entities import EntityId
from aidm.engines.base import Counter
from aidm.engines.loner3e.world import Loner3eGame, Loner3eSheet

KAEL = Loner3eSheet(id=EntityId("kael"), name="Kael", brief="", known=True)


def _state() -> Loner3eGame:
    """A counter card drops the name for the played character alone, so it needs the state."""
    _, state = initialized()
    return state


def test_counter_rejects_current_outside_its_bounds() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Counter(current=-1, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Counter(current=11, maximum=10)


def test_adjust_clamps_to_the_counters_bounds_and_reports_only_a_real_move() -> None:
    state = _state()
    KAEL.luck.current = 0
    (changed,) = KAEL.luck.change(KAEL, 99, "Luck", "the strain")
    assert (changed.card, KAEL.luck.current) == ("Kael: Luck +6 -> 6/6", 6)
    assert KAEL.luck.change(KAEL, 99, "Luck", "the strain") == []
    assert KAEL.luck.adjust(-2) == -2

    player = state.payload.player
    player.luck.current = 0
    (own,) = player.luck.change(player, 1, "Luck", "the strain")
    assert own.card == "Luck +1 -> 1/6"
