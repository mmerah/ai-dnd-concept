from random import Random

import pytest
from pydantic import ValidationError

from aidm.core.facts import DiceEvent, roll, roll_pool


def test_roll_traces_every_die() -> None:
    rolled, fact = roll((6, 6), "a forced door", Random(0))

    assert len(rolled) == 2
    assert fact.trace == f"a forced door: 2d6 [{rolled[0]}, {rolled[1]}]"


def test_a_dice_event_refuses_an_out_of_range_highlight() -> None:
    with pytest.raises(ValidationError):
        DiceEvent(label="Pool", faces=(6,), rolled=(4,), highlight=(1,))


def test_roll_pool_highlights_the_kept_die_only_in_a_pool() -> None:
    kept, event, _ = roll_pool((6, 6, 6), "a forced door", Random(0), label="Pool")

    assert kept == 4
    assert event.rolled == (4, 4, 1)
    assert event.highlight == (0,)

    _, single_event, _ = roll_pool((6,), "a forced door", Random(0), label="d6")

    assert single_event.highlight == ()
