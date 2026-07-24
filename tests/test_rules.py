from random import Random
from typing import get_args

import pytest
from pydantic import ValidationError

from aidm.domain.models import Ability, Attributes, Character, EntityId, RollDice
from aidm.engine import rules

KAEL = Character(
    name="Kael",
    attributes=Attributes(wisdom=14, strength=8),
    max_hp=10,
    hp=10,
    location_id=EntityId("here"),
)


def test_every_ability_is_an_attribute() -> None:
    """rules.modifier does getattr(attributes, ability); a divergence is a runtime error."""
    assert set(get_args(Ability)) == set(Attributes.model_fields)


def test_modifier() -> None:
    assert rules.modifier(KAEL.attributes, "wisdom") == 2
    assert rules.modifier(KAEL.attributes, "strength") == -1


def test_roll_check_adds_the_modifier_and_compares_to_the_dc() -> None:
    check = rules.roll_check(KAEL, "wisdom", dc=12, rng=Random(0))
    assert check.total == check.roll + 2
    assert check.success == (check.total >= 12)


def test_roll_dice_sums_faces_and_applies_the_modifier() -> None:
    total, event = rules.roll_dice("2d1+3", Random(0))  # 1 + 1 + 3, deterministic on d1
    assert (total, event.dice, event.total) == (5, "2d1+3", 5)


def test_roll_dice_rejects_a_malformed_spec() -> None:
    with pytest.raises(ValueError, match="malformed dice spec"):
        rules.roll_dice("not-dice", Random(0))


def test_the_dice_field_rejects_a_zero_face_die() -> None:
    """'1d0' would reach randint(1, 0) and crash; the shared pattern rejects it at the boundary."""
    for spec in ("1d0", "0d6"):
        with pytest.raises(ValidationError):
            RollDice(dice=spec, bind="x")
