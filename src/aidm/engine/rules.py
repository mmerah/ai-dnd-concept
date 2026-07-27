"""The ruleset: d20 plus the right bonus against a number, plus free-form dice."""

from random import Random

from ..domain.models import (
    Ability,
    ActorEntity,
    AttackRolled,
    Attributes,
    DcRolled,
    DiceRolled,
    RollKind,
)
from ..utils import dice

DIE = 20


def modifier(attributes: Attributes, ability: Ability) -> int:
    return (attributes[ability] - 10) // 2


def save_bonus(actor: ActorEntity, ability: Ability) -> int:
    """A monster's is snapshotted absolute from its record; a player's is the ability modifier plus
    the proficiency bonus, on the saves their class is good at and nowhere else."""
    absolute = actor.stats.saving_throws.get(ability)
    if absolute is not None:
        return absolute
    base = modifier(actor.stats.attributes, ability)
    progression = actor.progression
    if progression is not None and ability in progression.saving_throws:
        return base + progression.prof_bonus
    return base


def roll_check(actor: ActorEntity, ability: Ability, dc: int, rng: Random) -> DcRolled:
    return _rolled(actor, ability, dc, modifier(actor.stats.attributes, ability), "check", rng)


def roll_save(actor: ActorEntity, ability: Ability, dc: int, rng: Random) -> DcRolled:
    return _rolled(actor, ability, dc, save_bonus(actor, ability), "save", rng)


def roll_attack(
    actor: ActorEntity, target: ActorEntity, weapon: str, bonus: int, rng: Random
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
    actor: ActorEntity, ability: Ability, dc: int, bonus: int, kind: RollKind, rng: Random
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
    """`MOD` belongs to the caster, and no role supplies one yet: `SelfContainedDice` refuses it at
    the model boundary, so reaching it here is a broken plan, not a silent zero."""
    match term:
        case dice.DiceTerm(count=count, faces=faces):
            return sum(rng.randint(1, faces) for _ in range(count))
        case dice.ConstantTerm(value=value):
            return value
        case dice.ModifierTerm():
            raise ValueError(f"{dice.MOD} needs a caster's modifier, which nothing supplies")
