"""The ruleset: d20 + ability modifier against a DC, plus free-form dice."""

from random import Random

from ..domain.models import Ability, ActorEntity, Attributes, CheckRolled, DiceRolled
from ..utils import dice

DIE = 20


def modifier(attributes: Attributes, ability: Ability) -> int:
    return (attributes[ability] - 10) // 2


def roll_check(actor: ActorEntity, ability: Ability, dc: int, rng: Random) -> CheckRolled:
    roll = rng.randint(1, DIE)
    total = roll + modifier(actor.stats.attributes, ability)
    return CheckRolled(ability=ability, dc=dc, roll=roll, total=total, success=total >= dc)


def roll_dice(
    expression: dice.DiceExpr, rng: Random, ability_modifier: int | None = None
) -> tuple[int, DiceRolled]:
    total = sum(
        term.sign * _magnitude(term, rng, ability_modifier) for term in dice.terms(expression)
    )
    return total, DiceRolled(dice=expression, total=total)


def _magnitude(term: dice.Term, rng: Random, ability_modifier: int | None) -> int:
    """`MOD` with no modifier is a broken plan, not a silent zero."""
    match term:
        case dice.DiceTerm(count=count, faces=faces):
            return sum(rng.randint(1, faces) for _ in range(count))
        case dice.ConstantTerm(value=value):
            return value
        case dice.ModifierTerm():
            if ability_modifier is None:
                raise ValueError("a dice expression using MOD needs an ability modifier")
            return ability_modifier
