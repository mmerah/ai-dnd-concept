from dataclasses import dataclass
from random import Random
from typing import Literal

from aidm.base import PLAYER_ID
from aidm.facts import Fact

from . import dice
from .identity import ENGINE_ID
from .state import Dnd5eActor
from .values import Ability, Attributes

DIE = 20
RollKind = Literal["check", "save"]


@dataclass(frozen=True, slots=True)
class Rolled:
    """A d20 roll against a DC, with the branch it selects already decided."""

    fact: Fact
    success: bool


@dataclass(frozen=True, slots=True)
class Struck:
    """An attack roll, with whether it landed already decided."""

    fact: Fact
    hit: bool


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


def roll_check(actor: Dnd5eActor, ability: Ability, dc: int, rng: Random) -> Rolled:
    return _rolled(actor, ability, dc, modifier(actor.stats.attributes, ability), "check", rng)


def roll_save(actor: Dnd5eActor, ability: Ability, dc: int, rng: Random) -> Rolled:
    return _rolled(actor, ability, dc, save_bonus(actor, ability), "save", rng)


def roll_attack(
    actor: Dnd5eActor, target: Dnd5eActor, weapon: str, bonus: int, rng: Random
) -> Struck:
    roll = rng.randint(1, DIE)
    total = roll + bonus
    hit = total >= target.stats.ac
    fact = _attack_rolled(actor.name, target.name, weapon, roll, total, target.stats.ac, hit)
    return Struck(fact=fact, hit=hit)


def roll_dice(expression: dice.SelfContainedDice, rng: Random) -> tuple[int, Fact]:
    total = sum(term.sign * _magnitude(term, rng) for term in dice.terms(expression))
    return total, _dice_rolled(expression, total)


def _rolled(
    actor: Dnd5eActor, ability: Ability, dc: int, bonus: int, kind: RollKind, rng: Random
) -> Rolled:
    roll = rng.randint(1, DIE)
    total = roll + bonus
    success = total >= dc
    fact = _dc_rolled(actor, kind, ability, dc, roll, total, success)
    return Rolled(fact=fact, success=success)


def _magnitude(term: dice.Term, rng: Random) -> int:
    match term:
        case dice.DiceTerm(count=count, faces=faces):
            return sum(rng.randint(1, faces) for _ in range(count))
        case dice.ConstantTerm(value=value):
            return value
        case dice.ModifierTerm():
            raise ValueError(f"{dice.MOD} needs a caster's modifier, which nothing supplies")


def _dc_rolled(
    actor: Dnd5eActor,
    kind: RollKind,
    ability: Ability,
    dc: int,
    roll: int,
    total: int,
    success: bool,
) -> Fact:
    who = "" if actor.id == PLAYER_ID else f"{actor.name} "
    verdict = "SUCCESS" if success else "FAILURE"
    trace = f"{who}{ability} {kind}: {roll} -> {total} vs DC {dc}: {verdict}"
    return Fact(
        source=ENGINE_ID,
        kind="dc_rolled",
        trace=trace,
        narrator=f"{actor.name} {'succeeds' if success else 'fails'}",
        data={
            "actor_id": actor.id,
            "actor_name": actor.name,
            "roll_kind": kind,
            "ability": ability,
            "dc": dc,
            "roll": roll,
            "total": total,
            "success": success,
        },
    )


def _attack_rolled(
    actor_name: str, target_name: str, weapon: str, roll: int, total: int, ac: int, hit: bool
) -> Fact:
    outcome = "HIT" if hit else "MISS"
    trace = (
        f"{actor_name} attacks {target_name} with {weapon}: {roll} -> {total} vs ac {ac}: {outcome}"
    )
    return Fact(
        source=ENGINE_ID,
        kind="attack_rolled",
        trace=trace,
        narrator=f"{actor_name}'s attack {'hits' if hit else 'misses'} {target_name}",
        data={
            "actor_name": actor_name,
            "target_name": target_name,
            "weapon": weapon,
            "roll": roll,
            "total": total,
            "ac": ac,
            "hit": hit,
        },
    )


def _dice_rolled(expression: str, total: int) -> Fact:
    return Fact(
        source=ENGINE_ID,
        kind="dice_rolled",
        trace=f"rolled {expression}: {total}",
        narrator=None,
        data={"dice": expression, "total": total},
    )
