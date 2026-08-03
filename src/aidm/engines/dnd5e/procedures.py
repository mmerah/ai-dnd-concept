from random import Random

from aidm.world import GameState

from . import dice, features, rolls
from .access import carried_by
from .facts import AttackRolled
from .ruleset import AttackProfile, Ruleset, WeaponProfile
from .state import Dnd5eActor, Dnd5eItem, Progression
from .values import ContentSlug


def swing(state: GameState, attacker: Dnd5eActor, weapon: str, ruleset: Ruleset) -> AttackProfile:
    ref = attacker.ref
    archetype = None if ref is None else ruleset.archetype(ref)
    if archetype is not None:
        return _own_attack(archetype.attacks, attacker.name, weapon)
    return _wielded(state, attacker, weapon, ruleset)


def strike(
    attacker: Dnd5eActor, target: Dnd5eActor, swung: AttackProfile, rng: Random
) -> AttackRolled:
    return rolls.roll_attack(attacker, target, swung.name, swung.to_hit, rng)


def _own_attack(
    attacks: tuple[AttackProfile, ...], attacker_name: str, weapon: str
) -> AttackProfile:
    wanted = weapon.casefold()
    found = next((a for a in attacks if a.name.casefold() == wanted), None)
    if found is None:
        raise ValueError(
            f"{attacker_name} has no attack called {weapon!r}; it has {[a.name for a in attacks]}"
        )
    return found


def _wielded(
    state: GameState, attacker: Dnd5eActor, weapon: str, ruleset: Ruleset
) -> AttackProfile:
    item, profile = _held_weapon(state, attacker, weapon, ruleset)
    ability = "dexterity" if _uses_dexterity(profile, attacker) else "strength"
    bonus = rolls.modifier(attacker.stats.attributes, ability)
    return AttackProfile(
        name=item.name,  # roles see entity names, not record names
        to_hit=(
            bonus
            + _proficiency_bonus(attacker.progression, profile.index, ruleset)
            + features.ranged_attack_bonus(
                attacker.progression, attacker.stats.attributes, profile, ruleset
            )
        ),
        damage=None if profile.damage is None else _plus(profile.damage, bonus),
    )


def _held_weapon(
    state: GameState, attacker: Dnd5eActor, weapon: str, ruleset: Ruleset
) -> tuple[Dnd5eItem, WeaponProfile]:
    for item in carried_by(state, attacker.id):
        if item.ref is None or weapon.casefold() not in (item.name.casefold(), item.ref.index):
            continue
        found = ruleset.weapon(item.ref)
        if found is not None:
            return item, found
    raise ValueError(f"{attacker.name} carries no weapon called {weapon!r}")


def _uses_dexterity(weapon: WeaponProfile, attacker: Dnd5eActor) -> bool:
    if weapon.ranged:
        return True
    if not weapon.finesse:
        return False
    scores = attacker.stats.attributes
    return scores["dexterity"] > scores["strength"]


def _proficiency_bonus(
    progression: Progression | None, equipment: ContentSlug, ruleset: Ruleset
) -> int:
    if progression is None:
        return 0
    if not ruleset.proficient(progression.origin, progression.proficiencies, equipment):
        return 0
    return progression.prof_bonus


def _plus(expression: dice.DiceExpr, bonus: int) -> dice.SelfContainedDice:
    if bonus == 0:
        return expression
    return f"{expression} {'+' if bonus > 0 else '-'} {abs(bonus)}"
