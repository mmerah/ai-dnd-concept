from random import Random

from aidm.state.actions import roll_pool


def test_a_pool_keeps_its_highest_die_and_traces_every_one() -> None:
    event, fact = roll_pool((6, 6), "a forced door", Random(0), label="Pool")

    assert event.label == "Pool"
    assert event.faces == (6, 6)
    assert len(event.rolled) == 2
    assert event.kept == max(event.rolled)
    assert fact.kind == "dice_rolled"
    shown = f"{event.rolled[0]}, {event.rolled[1]}"
    assert fact.trace == f"a forced door: 2d6 [{shown}] -> {event.kept}"
