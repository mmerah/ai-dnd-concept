from random import Random

from aidm.state.dice import roll_pool, roll_sum


def test_a_pool_keeps_its_highest_die_and_traces_every_one() -> None:
    kept, fact = roll_pool((6, 6), "a forced door", Random(0))
    raw = fact.data["rolled"]
    assert isinstance(raw, list)
    dice = [die for die in raw if isinstance(die, int)]

    assert kept == max(dice)
    assert len(dice) == 2
    assert fact.trace == f"a forced door: 2d6 [{dice[0]}, {dice[1]}] -> {kept}"
    assert fact.data["faces"] == [6, 6]


def test_a_summed_roll_totals_every_die_and_traces_them() -> None:
    total, fact = roll_sum((6, 6, 6), "a fresh recruit's strength", Random(0))
    raw = fact.data["rolled"]
    assert isinstance(raw, list)
    dice = [die for die in raw if isinstance(die, int)]

    assert total == sum(dice)
    assert len(dice) == 3
    assert fact.trace.startswith("a fresh recruit's strength: 3d6 [")
    assert fact.trace.endswith(f"-> {total}")
