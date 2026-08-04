from collections.abc import Mapping

from pydantic_ai import ModelRetry

from aidm.core.base import EntityId
from aidm.core.facts import Fact

from . import dice, mechanics, rolls
from .access import Dnd5eWorld
from .content.library import ContentMiss
from .content.records.base import ContentRef
from .content.records.spells import SpellDamage, SpellLevel, SpellRecord, SpellSave
from .content.vocabulary import RestType
from .identity import ENGINE_ID
from .ruleset import ProgressionRules, Ruleset, SpellcastingProfile, SpellProfile
from .state import Dnd5eActor, Progression, ResourceState, SpellKey, spell_ref

SAVE_DC_BASE = 8


def slots(
    held: Mapping[int, ResourceState],
    maxima: Mapping[int, int],
    casting: SpellcastingProfile | None,
) -> dict[int, ResourceState]:
    """Recompute the slot pools for a level, carrying what each level had already spent."""
    if not maxima:
        return {}
    if casting is None:
        raise ValueError("a class with spell slots declares no spellcasting")
    spent = {level: state.spent for level, state in held.items()}
    return {
        level: ResourceState(
            remaining=max(0, maximum - spent.get(level, 0)),
            maximum=maximum,
            recharge=casting.slot_recharge,
        )
        for level, maximum in maxima.items()
    }


def recharged(world: Dnd5eWorld, completed: RestType) -> tuple[int, ...]:
    spent = [
        (level, state)
        for level, state in sorted(world.progression().spell_slots.items())
        if state.refills(completed)
    ]
    for _, state in spent:
        state.remaining = state.maximum
    return tuple(level for level, _ in spent)


def spellcasting(progression: Progression, ruleset: ProgressionRules) -> SpellcastingProfile:
    casting = ruleset.character(progression.origin).spellcasting
    if casting is None:
        raise ModelRetry(f"class {progression.origin.class_ref.index!r} casts no spells")
    return casting


def repertoire(
    progression: Progression, casting: SpellcastingProfile, ruleset: Ruleset
) -> tuple[SpellProfile, ...]:
    chosen = set(progression.chosen_spells)
    prepared = range(1, max(progression.spell_slots, default=0) + 1)
    return tuple(
        spell
        for spell in ruleset.spell_list(progression.origin)
        if spell.ref in chosen or (casting.prepares and spell.level in prepared)
    )


def cast(
    world: Dnd5eWorld, spell: SpellKey, slot_level: SpellLevel, target_id: EntityId | None
) -> list[Fact]:
    progression = world.progression()
    casting = spellcasting(progression, world.ruleset)
    ref = spell_ref(spell)
    record = _castable(world, ref, casting)
    # resolved even when the record types no effect to aim
    target = world.target(target_id)
    spent: list[Fact] = [
        *_spend(progression, record, slot_level),
        _spell_cast(ref, record.name, slot_level),
    ]
    return [*spent, *_effects(world, slot_level, target, record, casting)]


def _spell_cast(ref: ContentRef, name: str, slot_level: int) -> Fact:
    at = "" if slot_level == 0 else f" at level {slot_level}"
    trace = f"cast {name}{at}"
    return Fact(
        source=ENGINE_ID,
        kind="spell_cast",
        trace=trace,
        narrator=f"cast {name}",
        data={"ref": str(ref), "name": name, "slot_level": slot_level},
    )


def _castable(world: Dnd5eWorld, ref: ContentRef, casting: SpellcastingProfile) -> SpellRecord:
    if not any(
        spell.ref == ref for spell in repertoire(world.progression(), casting, world.ruleset)
    ):
        raise ModelRetry(f"the player cannot cast {ref.index!r}")
    found = world.ruleset.spell(ref)
    if isinstance(found, ContentMiss):
        raise ValueError(found.summary)
    return found


def _spend(progression: Progression, record: SpellRecord, slot_level: int) -> list[Fact]:
    if record.level == 0:
        if slot_level != 0:
            raise ModelRetry(f"cantrip {record.index!r} spends no spell slot")
        return []
    if slot_level < record.level:
        raise ModelRetry(
            f"spell {record.index!r} is level {record.level}; a level {slot_level} slot is too low"
        )
    state = progression.spell_slots.get(slot_level)
    if state is None:
        raise ModelRetry(f"the player has no level {slot_level} spell slots")
    if state.remaining == 0:
        raise ModelRetry(
            f"no level {slot_level} spell slot remains; finish a {state.recharge} rest"
        )
    state.remaining -= 1
    return [_spell_slot_spent(slot_level, state)]


def _spell_slot_spent(slot_level: int, state: ResourceState) -> Fact:
    trace = f"spent a level {slot_level} spell slot ({state.remaining}/{state.maximum} remaining)"
    return Fact(
        source=ENGINE_ID,
        kind="spell_slot_spent",
        trace=trace,
        narrator=None,
        data={"slot_level": slot_level, "remaining": state.remaining, "maximum": state.maximum},
    )


def _effects(
    world: Dnd5eWorld,
    slot_level: SpellLevel,
    target: Dnd5eActor,
    record: SpellRecord,
    casting: SpellcastingProfile,
) -> list[Fact]:
    """Resolve only what the record types; anything else the spell does stays description-guided."""
    progression = world.progression()
    modifier = rolls.modifier(world.player().stats.attributes, casting.ability)
    healing = _scaled(record.heal_at_slot_level, slot_level)
    if healing is not None:
        healed = dice.substituted(healing, modifier)
        return mechanics.hp_facts(world, target.id, healed, sign=1)
    harm = _harm(record.damage, slot_level, progression.level)
    amount = None if harm is None else dice.substituted(harm, modifier)
    if record.attack_type is not None:
        bonus = progression.prof_bonus + modifier
        return _attacked(world, _aimed(world, target, record), record.name, bonus, amount)
    if record.save is not None:
        dc = SAVE_DC_BASE + progression.prof_bonus + modifier
        return _saved(world, _aimed(world, target, record), record.save, dc, amount)
    if amount is None:
        return []
    return mechanics.hp_facts(world, target.id, amount, sign=-1)


def _harm(damage: SpellDamage | None, slot_level: int, class_level: int) -> dice.DiceExpr | None:
    """A cantrip scales off the caster's level; everything else off the slot it was cast from."""
    if damage is None:
        return None
    if slot_level == 0:
        return _scaled(damage.at_character_level, class_level)
    return _scaled(damage.at_slot_level, slot_level)


def _scaled(table: Mapping[int, dice.DiceExpr], reached: int) -> dice.DiceExpr | None:
    """Take the highest step the level reaches, so a spell that does not upcast still resolves."""
    steps = [expression for at, expression in sorted(table.items()) if at <= reached]
    return steps[-1] if steps else None


def _aimed(world: Dnd5eWorld, target: Dnd5eActor, record: SpellRecord) -> Dnd5eActor:
    """A roll needs someone other than the caster on the far side of it."""
    if target.id == world.player().id:
        raise ModelRetry(f"spell {record.index!r} needs a target other than the caster")
    return target


def _attacked(
    world: Dnd5eWorld,
    target: Dnd5eActor,
    name: str,
    bonus: int,
    amount: dice.SelfContainedDice | None,
) -> list[Fact]:
    struck = rolls.roll_attack(world.player(), target, name, bonus, world.rng)
    seen: list[Fact] = [*mechanics.reveal(world, target), struck.fact]
    if not struck.hit or amount is None:
        return seen
    return [*seen, *mechanics.hp_facts(world, target.id, amount, sign=-1)]


def _saved(
    world: Dnd5eWorld,
    target: Dnd5eActor,
    save: SpellSave,
    dc: int,
    amount: dice.SelfContainedDice | None,
) -> list[Fact]:
    rolled = rolls.roll_save(target, save.ability, dc, world.rng)
    seen: list[Fact] = [*mechanics.reveal(world, target), rolled.fact]
    if amount is None:
        return seen
    if not rolled.success:
        return [*seen, *mechanics.hp_facts(world, target.id, amount, sign=-1)]
    if save.on_success != "half":
        # `other` is a spell-specific consequence, which stays with the description.
        return seen
    total, halving = rolls.roll_dice(amount, world.rng)
    return [*seen, halving, *mechanics.hp_facts(world, target.id, total // 2, sign=-1)]
