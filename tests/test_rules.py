from random import Random

import pytest
from pydantic import ValidationError

from aidm.domain.models import PLAYER_ID, ActorEntity, Attributes, EntityId, RollDice, StatBlock
from aidm.engine import rules

KAEL = ActorEntity(
    id=PLAYER_ID,
    name="Kael",
    brief="A relic-hunter.",
    known=True,
    location_id=EntityId("here"),
    stats=StatBlock(attributes=Attributes(wisdom=14, strength=8), max_hp=10, hp=10),
)


def test_modifier() -> None:
    assert rules.modifier(KAEL.stats.attributes, "wisdom") == 2
    assert rules.modifier(KAEL.stats.attributes, "strength") == -1


def test_roll_check_adds_the_modifier_and_compares_to_the_dc() -> None:
    check = rules.roll_check(KAEL, "wisdom", dc=12, rng=Random(0))
    assert check.total == check.roll + 2
    assert check.success == (check.total >= 12)


@pytest.mark.parametrize(
    ("expression", "total"),
    [
        ("2d1+3", 5),  # d1 is deterministic, so every total below is exact
        ("2d1 + 4d1", 6),  # the multi-term sum the old single-term pattern could not express
        ("1d1-1", 0),
        ("10", 10),  # a bare constant: 61 of the pack's heal values are exactly this
    ],
)
def test_roll_dice_sums_every_term(expression: str, total: int) -> None:
    rolled, event = rules.roll_dice(expression, Random(0))
    assert (rolled, event.total) == (total, total)


def test_mod_is_substituted_at_roll_time() -> None:
    """`MOD` belongs to the actor, not the expression, so the roller supplies it."""
    assert rules.roll_dice("1d1 + MOD", Random(0), ability_modifier=3)[0] == 4
    with pytest.raises(ValueError, match="needs an ability modifier"):
        rules.roll_dice("1d8 + MOD", Random(0))


def test_a_malformed_expression_fails_at_its_boundary() -> None:
    """The parse is the validation, so a bad expression never reaches a roll."""
    for expression in ("not-dice", "1d0", "0d6", "2d6 +", "1d6 + + 2"):
        with pytest.raises(ValidationError):
            RollDice(dice=expression, bind="x")
