from aidm.core.facts import DICE, DiceEvent, Fact
from aidm.ui.dice import rolled_since, thrown

TWO_D6 = DiceEvent(label="2d6", faces=(6, 6), rolled=(2, 5))
KEPT_HIGHEST = DiceEvent(label="Action", faces=(8, 8), rolled=(3, 7), highlight=(1,))


def _fact(dice: DiceEvent, *, told: bool) -> Fact:
    return Fact(kind=DICE, trace=dice.label, told=told, card=dice.label, dice=(dice,))


def test_every_rolled_value_is_one_die_in_event_order() -> None:
    assert thrown((TWO_D6, KEPT_HIGHEST)) == [
        {"faces": 6, "value": 2},
        {"faces": 6, "value": 5},
        {"faces": 8, "value": 3},
        {"faces": 8, "value": 7},
    ]


def test_only_the_told_dice_landing_after_the_seen_facts_are_thrown() -> None:
    facts = (_fact(TWO_D6, told=True), _fact(TWO_D6, told=False), _fact(KEPT_HIGHEST, told=True))

    assert rolled_since(facts, 1) == (KEPT_HIGHEST,)
    assert rolled_since(facts, 0) == (TWO_D6, KEPT_HIGHEST)
    assert rolled_since(facts, 3) == ()
