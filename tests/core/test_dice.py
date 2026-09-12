from random import Random

import pytest
from pydantic import ValidationError

from aidm.core.facts import DiceEvent, roll, roll_pool


def test_roll_traces_every_die() -> None:
    rolled = roll((6, 6), "a forced door", Random(0))

    assert len(rolled.event.rolled) == 2
    assert (
        rolled.fact.trace
        == f"a forced door: 2d6 [{rolled.event.rolled[0]}, {rolled.event.rolled[1]}]"
    )


def test_roll_labels_a_single_die_by_notation_unless_given_one() -> None:
    rolled = roll((10,), "a listen check", Random(0))

    assert rolled.fact.trace == f"a listen check: d10 [{rolled.event.rolled[0]}]"
    assert rolled.event.label == "d10"

    labelled = roll((10,), "a listen check", Random(0), label="Listen")

    assert labelled.event.label == "Listen"


def test_a_dice_event_refuses_an_out_of_range_highlight() -> None:
    with pytest.raises(ValidationError):
        DiceEvent(label="Pool", faces=(6,), rolled=(4,), highlight=(1,))


def test_roll_pool_highlights_the_kept_die_only_in_a_pool() -> None:
    rolled = roll_pool((6, 6, 6), "a forced door", Random(0), label="Pool")

    assert rolled.kept == 4
    assert rolled.event.rolled == (4, 4, 1)
    assert rolled.event.highlight == (0,)

    single = roll_pool((6,), "a forced door", Random(0), label="d6")

    assert single.event.highlight == ()


def test_rolled_total_sums_the_pool() -> None:
    rolled = roll_pool((6, 6, 6), "a forced door", Random(0), label="Pool")

    assert rolled.total == sum(rolled.event.rolled)


def test_face_gives_the_single_die_and_refuses_a_pool() -> None:
    rolled = roll((10,), "a listen check", Random(0))

    assert rolled.face == rolled.event.rolled[0]

    pool = roll_pool((6, 6), "a forced door", Random(0))
    with pytest.raises(ValueError, match="rolled 2 dice, not one"):
        _ = pool.face
