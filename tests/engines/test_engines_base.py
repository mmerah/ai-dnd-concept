import pytest
from pydantic import ValidationError
from support.game import initialized

from aidm.engines.base import (
    Gauge,
    Thing,
    named_unmet,
)
from aidm.engines.loner3e.world import Loner3eEntity, Loner3eGame

KAEL = Loner3eEntity(id="kael", name="Kael", brief="", known=True)


def _state() -> Loner3eGame:
    """A counter card drops the name for the played character alone, so it needs the state."""
    _, state = initialized()
    return state


def test_counter_rejects_current_outside_its_bounds() -> None:
    with pytest.raises(ValidationError, match="below zero"):
        Gauge(current=-1, maximum=10)
    with pytest.raises(ValidationError, match="above maximum"):
        Gauge(current=11, maximum=10)


def test_adjust_clamps_to_the_counters_bounds_and_reports_only_a_real_move() -> None:
    state = _state()
    KAEL.luck.current = 0
    (changed,) = KAEL.change(KAEL.luck, 99, "Luck", "the strain")
    assert (changed.card, KAEL.luck.current) == ("Kael: Luck +6 → 6/6", 6)
    assert KAEL.change(KAEL.luck, 99, "Luck", "the strain") == []
    assert KAEL.luck.adjust(-2) == -2

    player = state.world.player
    player.luck.current = 0
    (own,) = player.change(player.luck, 1, "Luck", "the strain")
    assert own.card == "Luck +1 → 1/6"


def test_named_unmet_finds_whole_words_and_phrases_case_folded() -> None:
    text = "The Bell Tower looms over the square; a bell rings, and old-tom watches."
    entities = [
        Thing(id="bell-tower", name="Bell Tower", brief=""),
        Thing(id="the-bell", name="Bell", brief=""),
        Thing(id="town-square", name="town square", brief=""),
        Thing(id="old-tom", name="Tom", brief=""),
    ]
    assert named_unmet(text, entities) == ["Bell Tower", "Bell", "Tom"]
