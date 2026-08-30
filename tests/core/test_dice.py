from random import Random

import pytest
from pydantic import ValidationError

from aidm.engines.core import keep_highest
from aidm.state.facts import DiceEvent, roll


def test_roll_traces_every_die() -> None:
    rolled, fact = roll((6, 6), "a forced door", Random(0))

    assert len(rolled) == 2
    assert fact.kind == "dice_rolled"
    assert fact.trace == f"a forced door: 2d6 [{rolled[0]}, {rolled[1]}]"


def test_a_dice_event_refuses_an_out_of_range_highlight() -> None:
    with pytest.raises(ValidationError):
        DiceEvent(label="Pool", faces=(6,), rolled=(4,), highlight=(1,))


def test_keep_highest_results_in_the_highest_rolled_die() -> None:
    kept, event, _ = keep_highest((6, 6, 6), "a forced door", Random(0), label="Pool")

    assert kept == 4
    assert event.rolled == (4, 4, 1)
    assert max(event.rolled) == 4
    assert event.highlight == (0,)
