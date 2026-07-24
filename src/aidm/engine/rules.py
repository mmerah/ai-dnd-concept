"""The ruleset: d20 + ability modifier against a DC."""

from random import Random

from ..domain.models import Ability, Attributes, Character, CheckRolled

DIE = 20


def modifier(attributes: Attributes, ability: Ability) -> int:
    return (getattr(attributes, ability) - 10) // 2


def roll_check(character: Character, ability: Ability, dc: int, rng: Random) -> CheckRolled:
    roll = rng.randint(1, DIE)
    total = roll + modifier(character.attributes, ability)
    return CheckRolled(ability=ability, dc=dc, roll=roll, total=total, success=total >= dc)
