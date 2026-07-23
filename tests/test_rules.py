from random import Random

from aidm.domain.models import Attributes, Character
from aidm.engine import rules

KAEL = Character(name="Kael", attributes=Attributes(wisdom=14, strength=8), location="here")


def test_modifier() -> None:
    assert rules.modifier(KAEL.attributes, "wisdom") == 2
    assert rules.modifier(KAEL.attributes, "strength") == -1


def test_roll_check_adds_the_modifier_and_compares_to_the_dc() -> None:
    check = rules.roll_check(KAEL, "wisdom", dc=12, rng=Random(0))
    assert check.total == check.roll + 2
    assert check.success == (check.total >= 12)
