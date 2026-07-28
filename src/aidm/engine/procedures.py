"""The 5e compound procedures: what a proposal to strike someone resolves into.

This is the reason progression had to land first. A monster's to-hit and damage sit on its record;
the player's are an ability modifier plus a proficiency bonus, and only a class and a level know
either. Which end of that an actor is at is the only branch here.

The chain of events an attack produces is assembled in `resolve.py`, alongside every other
consequence's — this module answers only what the swing is worth."""

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random

from ..content import ContentMiss, ContentRef, Library, MonsterAttack, MonsterRecord
from ..content.records import DamageRoll, EquipmentProficiency, WeaponRecord
from ..domain.models import ActorEntity, AttackRolled, GameState, ItemEntity, Progression
from ..utils import dice
from . import rules


@dataclass(frozen=True, slots=True)
class Swing:
    """One resolved attack: what to add to the d20, and everything rolled on a hit. `damage` is
    `None` for a weapon that deals none — the net restrains and nothing else."""

    weapon: str
    to_hit: int
    damage: dice.SelfContainedDice | None


def swing(state: GameState, attacker: ActorEntity, weapon: str, library: Library) -> Swing:
    """An actor backed by a record strikes with one of its own attacks; anyone else strikes with a
    weapon they carry. Matched by name, because a name is what every role was shown."""
    ref = attacker.ref
    record = None if ref is None else library.monster(ref)
    if isinstance(record, MonsterRecord):
        return _own_attack(record, weapon)
    return _wielded(state, attacker, weapon, library)


def strike(attacker: ActorEntity, target: ActorEntity, swung: Swing, rng: Random) -> AttackRolled:
    return rules.roll_attack(attacker, target, swung.weapon, swung.to_hit, rng)


def _own_attack(record: MonsterRecord, weapon: str) -> Swing:
    """A record's damage dice already include its own modifier — the goblin's scimitar is
    `1d6+2` — so nothing is added to them here."""
    wanted = weapon.casefold()
    actions = (*record.actions, *record.legendary_actions, *record.reactions)
    attacks = [a for a in actions if isinstance(a, MonsterAttack)]
    found = next((a for a in attacks if a.name.casefold() == wanted), None)
    if found is None:
        raise ValueError(
            f"{record.name} has no attack called {weapon!r}; it has {[a.name for a in attacks]}"
        )
    return Swing(weapon=found.name, to_hit=found.attack_bonus, damage=_summed(found.damage))


def _wielded(state: GameState, attacker: ActorEntity, weapon: str, library: Library) -> Swing:
    """The dice come from the weapon's record; the modifier and the proficiency bonus come from the
    wielder, which is what nothing could supply before progression."""
    item, record = _held_weapon(state, attacker, weapon, library)
    ability = "dexterity" if _uses_dexterity(record, attacker) else "strength"
    bonus = rules.modifier(attacker.stats.attributes, ability)
    progression = attacker.progression
    proficiency = 0 if progression is None else _proficiency_bonus(progression, record, library)
    to_hit = bonus + proficiency
    return Swing(
        # The entity's name, not the record's: the fiction is what the player was ever told about.
        weapon=item.name,
        to_hit=to_hit,
        damage=None if record.damage is None else _plus(record.damage.dice, bonus),
    )


def _held_weapon(
    state: GameState, attacker: ActorEntity, weapon: str, library: Library
) -> tuple[ItemEntity, WeaponRecord]:
    wanted = weapon.casefold()
    for item in state.world.carried_by(attacker.id):
        if item.ref is None:
            continue
        if wanted not in (item.name.casefold(), item.ref.index):
            continue
        found = library.weapon(item.ref)
        if not isinstance(found, ContentMiss):
            return item, found
    raise ValueError(f"{attacker.name} carries no weapon called {weapon!r}")


def _uses_dexterity(record: WeaponRecord, attacker: ActorEntity) -> bool:
    """A ranged weapon has no choice; finesse gives the wielder one, so take the better score."""
    if record.weapon_range == "Ranged":
        return True
    if "finesse" not in record.properties:
        return False
    scores = attacker.stats.attributes
    return scores["dexterity"] > scores["strength"]


def _proficiency_bonus(progression: Progression, weapon: WeaponRecord, library: Library) -> int:
    """Zero unless one of the actor's proficiencies covers this weapon. Each proficiency already
    lists the equipment it covers — an `equipment_category` was expanded to its members at import —
    so nothing re-derives a category mid-turn."""
    pack = progression.origin.class_ref.pack
    for index in progression.proficiencies:
        found = library.proficiency(ContentRef(pack=pack, collection="proficiencies", index=index))
        if isinstance(found, EquipmentProficiency) and weapon.index in found.equipment:
            return progression.prof_bonus
    return 0


def _summed(rolls: Sequence[DamageRoll]) -> dice.SelfContainedDice | None:
    """Summed across damage types: nothing resists one yet, so keeping them apart would be a
    distinction no rule could act on."""
    return " + ".join(roll.dice for roll in rolls) if rolls else None


def _plus(expression: str, bonus: int) -> dice.SelfContainedDice:
    if bonus == 0:
        return expression
    return f"{expression} {'+' if bonus > 0 else '-'} {abs(bonus)}"
