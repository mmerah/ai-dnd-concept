from random import Random

from aidm.state.actions import roll_pool


def test_a_pool_keeps_its_highest_die_and_traces_every_one() -> None:
    kept, fact = roll_pool((6, 6), "a forced door", Random(0), role="pool")
    raw = fact.data["rolled"]
    assert isinstance(raw, list)
    dice = [die for die in raw if isinstance(die, int)]

    assert kept == max(dice)
    assert len(dice) == 2
    assert fact.trace == f"a forced door: 2d6 [{dice[0]}, {dice[1]}] -> {kept}"
    assert fact.data["faces"] == [6, 6]
