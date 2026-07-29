from random import Random

from ..domain.models.entities import ActorEntity, ItemEntity
from ..domain.models.events import AttackRolled
from ..domain.models.progression import Progression
from ..domain.models.state import GameState
from ..utils import dice
from ..utils.models import Slug
from . import rules
from .ruleset import AttackProfile, CombatRules, WeaponProfile


def swing(
    state: GameState, attacker: ActorEntity, weapon: str, ruleset: CombatRules
) -> AttackProfile:
    ref = attacker.ref
    archetype = None if ref is None else ruleset.archetype(ref)
    if archetype is not None:
        return _own_attack(archetype.attacks, attacker.name, weapon)
    return _wielded(state, attacker, weapon, ruleset)


def strike(
    attacker: ActorEntity, target: ActorEntity, swung: AttackProfile, rng: Random
) -> AttackRolled:
    return rules.roll_attack(attacker, target, swung.name, swung.to_hit, rng)


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
    state: GameState, attacker: ActorEntity, weapon: str, ruleset: CombatRules
) -> AttackProfile:
    item, profile = _held_weapon(state, attacker, weapon, ruleset)
    ability = "dexterity" if _uses_dexterity(profile, attacker) else "strength"
    bonus = rules.modifier(attacker.stats.attributes, ability)
    return AttackProfile(
        name=item.name,  # roles see entity names, not record names
        to_hit=bonus + _proficiency_bonus(attacker.progression, profile.index, ruleset),
        damage=None if profile.damage is None else _plus(profile.damage, bonus),
    )


def _held_weapon(
    state: GameState, attacker: ActorEntity, weapon: str, ruleset: CombatRules
) -> tuple[ItemEntity, WeaponProfile]:
    for item in state.world.carried_by(attacker.id):
        if item.ref is None or weapon.casefold() not in (item.name.casefold(), item.ref.index):
            continue
        found = ruleset.weapon(item.ref)
        if found is not None:
            return item, found
    raise ValueError(f"{attacker.name} carries no weapon called {weapon!r}")


def _uses_dexterity(weapon: WeaponProfile, attacker: ActorEntity) -> bool:
    if weapon.ranged:
        return True
    if not weapon.finesse:
        return False
    scores = attacker.stats.attributes
    return scores["dexterity"] > scores["strength"]


def _proficiency_bonus(
    progression: Progression | None, equipment: Slug, ruleset: CombatRules
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
