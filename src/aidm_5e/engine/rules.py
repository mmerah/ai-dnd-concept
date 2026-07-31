from random import Random

from ..domain.models.events import AttackRolled, DcRolled, DiceRolled, RollKind
from ..models import Dnd5eActor
from ..utils import dice
from ..utils.models import Ability, Attributes

DIE = 20


def modifier(attributes: Attributes, ability: Ability) -> int:
    return (attributes[ability] - 10) // 2


def save_bonus(actor: Dnd5eActor, ability: Ability) -> int:
    absolute = actor.stats.saving_throws.get(ability)
    if absolute is not None:
        return absolute
    base = modifier(actor.stats.attributes, ability)
    progression = actor.progression
    if progression is not None and ability in progression.saving_throws:
        return base + progression.prof_bonus
    return base


def roll_check(actor: Dnd5eActor, ability: Ability, dc: int, rng: Random) -> DcRolled:
    return _rolled(actor, ability, dc, modifier(actor.stats.attributes, ability), "check", rng)


def roll_save(actor: Dnd5eActor, ability: Ability, dc: int, rng: Random) -> DcRolled:
    return _rolled(actor, ability, dc, save_bonus(actor, ability), "save", rng)


def roll_attack(
    actor: Dnd5eActor, target: Dnd5eActor, weapon: str, bonus: int, rng: Random
) -> AttackRolled:
    roll = rng.randint(1, DIE)
    total = roll + bonus
    return AttackRolled(
        actor_name=actor.name,
        target_name=target.name,
        weapon=weapon,
        roll=roll,
        total=total,
        ac=target.stats.ac,
        hit=total >= target.stats.ac,
    )


def roll_dice(expression: dice.SelfContainedDice, rng: Random) -> tuple[int, DiceRolled]:
    total = sum(term.sign * _magnitude(term, rng) for term in dice.terms(expression))
    return total, DiceRolled(dice=expression, total=total)


def _rolled(
    actor: Dnd5eActor, ability: Ability, dc: int, bonus: int, kind: RollKind, rng: Random
) -> DcRolled:
    roll = rng.randint(1, DIE)
    total = roll + bonus
    return DcRolled(
        actor_id=actor.id,
        actor_name=actor.name,
        kind=kind,
        ability=ability,
        dc=dc,
        roll=roll,
        total=total,
        success=total >= dc,
    )


def _magnitude(term: dice.Term, rng: Random) -> int:
    match term:
        case dice.DiceTerm(count=count, faces=faces):
            return sum(rng.randint(1, faces) for _ in range(count))
        case dice.ConstantTerm(value=value):
            return value
        case dice.ModifierTerm():
            raise ValueError(f"{dice.MOD} needs a caster's modifier, which nothing supplies")
