"""The ruleset: d20 + ability modifier against a DC, plus free-form dice."""

import re
from random import Random

from ..domain.models import DICE_PATTERN, Ability, Attributes, Character, CheckRolled, DiceRolled

DIE = 20
_DICE = re.compile(DICE_PATTERN)


def modifier(attributes: Attributes, ability: Ability) -> int:
    return (getattr(attributes, ability) - 10) // 2


def roll_check(character: Character, ability: Ability, dc: int, rng: Random) -> CheckRolled:
    roll = rng.randint(1, DIE)
    total = roll + modifier(character.attributes, ability)
    return CheckRolled(ability=ability, dc=dc, roll=roll, total=total, success=total >= dc)


def roll_dice(spec: str, rng: Random) -> tuple[int, DiceRolled]:
    m = _DICE.match(spec)
    if m is None:
        raise ValueError(f"malformed dice spec {spec!r}")  # the validator catches it first
    count, faces, mod = int(m[1]), int(m[2]), int(m[3] or 0)
    total = sum(rng.randint(1, faces) for _ in range(count)) + mod
    return total, DiceRolled(dice=spec, total=total)
