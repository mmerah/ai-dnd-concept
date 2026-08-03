from collections.abc import Mapping

from aidm.facts import Fact

from . import dice, rolls
from .content.library import ContentMiss
from .content.records.base import ContentRef
from .content.records.spells import SpellDamage, SpellRecord, SpellSave
from .content.vocabulary import RestType
from .direction import Cast
from .identity import ENGINE_ID
from .mechanics import common, health
from .mechanics.resolution import Resolution
from .ruleset import ProgressionRules, Ruleset, SpellcastingProfile, SpellProfile
from .state import Dnd5eActor, Progression, ResourceState, spell_ref

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


def recharged(ctx: Resolution, completed: RestType) -> tuple[int, ...]:
    spent = [
        (level, state)
        for level, state in sorted(ctx.progression.spell_slots.items())
        if state.refills(completed)
    ]
    for _, state in spent:
        state.remaining = state.maximum
    return tuple(level for level, _ in spent)


def spellcasting(progression: Progression, ruleset: ProgressionRules) -> SpellcastingProfile:
    casting = ruleset.character(progression.origin).spellcasting
    if casting is None:
        raise ValueError(f"class {progression.origin.class_ref.index!r} casts no spells")
    return casting


def repertoire(
    progression: Progression, casting: SpellcastingProfile, ruleset: Ruleset
) -> tuple[SpellProfile, ...]:
    """Every spell the player may cast: the ones they chose, plus — for a prepared caster, whose
    preparation is not modelled — their whole class list up to the highest slot they hold."""
    chosen = set(progression.chosen_spells)
    prepared = range(1, max(progression.spell_slots, default=0) + 1)
    return tuple(
        spell
        for spell in ruleset.spell_list(progression.origin)
        if spell.ref in chosen or (casting.prepares and spell.level in prepared)
    )


def cast(ctx: Resolution, consequence: Cast) -> list[Fact]:
    progression = ctx.progression
    casting = spellcasting(progression, ctx.ruleset)
    ref = spell_ref(consequence.spell)
    record = _castable(ctx, ref, casting)
    spent: list[Fact] = [
        *_spend(progression, record, consequence.slot_level),
        _spell_cast(ref, record.name, consequence.slot_level),
    ]
    return [*spent, *_effects(ctx, consequence, record, casting)]


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


def _castable(ctx: Resolution, ref: ContentRef, casting: SpellcastingProfile) -> SpellRecord:
    if not any(spell.ref == ref for spell in repertoire(ctx.progression, casting, ctx.ruleset)):
        raise ValueError(f"the player cannot cast {ref.index!r}")
    found = ctx.ruleset.spell(ref)
    if isinstance(found, ContentMiss):
        raise ValueError(found.summary)
    return found


def _spend(progression: Progression, record: SpellRecord, slot_level: int) -> list[Fact]:
    if record.level == 0:
        if slot_level != 0:
            raise ValueError(f"cantrip {record.index!r} spends no spell slot")
        return []
    if slot_level < record.level:
        raise ValueError(
            f"spell {record.index!r} is level {record.level}; a level {slot_level} slot is too low"
        )
    state = progression.spell_slots.get(slot_level)
    if state is None:
        raise ValueError(f"the player has no level {slot_level} spell slots")
    if state.remaining == 0:
        raise ValueError(
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
    ctx: Resolution, consequence: Cast, record: SpellRecord, casting: SpellcastingProfile
) -> list[Fact]:
    """Resolve only what the record types; anything else the spell does stays description-guided."""
    progression = ctx.progression
    modifier = rolls.modifier(ctx.player.stats.attributes, casting.ability)
    slot_level = consequence.slot_level
    healing = _scaled(record.heal_at_slot_level, slot_level)
    if healing is not None:
        healed = dice.substituted(healing, modifier)
        return health.hp_facts(ctx, consequence.target_id, healed, sign=1)
    harm = _harm(record.damage, slot_level, progression.level)
    amount = None if harm is None else dice.substituted(harm, modifier)
    # Three spells state both an attack and a save, where the save is a later stage their
    # description owns; the attack roll is the one that decides whether the spell lands at all.
    if record.attack_type is not None:
        bonus = progression.prof_bonus + modifier
        return _attacked(ctx, _aimed(ctx, consequence, record), record.name, bonus, amount)
    if record.save is not None:
        dc = SAVE_DC_BASE + progression.prof_bonus + modifier
        return _saved(ctx, _aimed(ctx, consequence, record), record.save, dc, amount)
    if amount is None:
        return []
    return health.hp_facts(ctx, consequence.target_id, amount, sign=-1)


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


def _aimed(ctx: Resolution, consequence: Cast, record: SpellRecord) -> Dnd5eActor:
    """A roll needs someone other than the caster on the far side of it."""
    target = ctx.target(consequence.target_id)
    if target.id == ctx.player.id:
        raise ValueError(f"spell {record.index!r} needs a target other than the caster")
    return target


def _attacked(
    ctx: Resolution,
    target: Dnd5eActor,
    name: str,
    bonus: int,
    amount: dice.SelfContainedDice | None,
) -> list[Fact]:
    struck = rolls.roll_attack(ctx.player, target, name, bonus, ctx.rng)
    seen: list[Fact] = [*common.reveal(ctx, target), struck.fact]
    if not struck.hit or amount is None:
        return seen
    return [*seen, *health.hp_facts(ctx, target.id, amount, sign=-1)]


def _saved(
    ctx: Resolution,
    target: Dnd5eActor,
    save: SpellSave,
    dc: int,
    amount: dice.SelfContainedDice | None,
) -> list[Fact]:
    rolled = rolls.roll_save(target, save.ability, dc, ctx.rng)
    seen: list[Fact] = [*common.reveal(ctx, target), rolled.fact]
    if amount is None:
        return seen
    if not rolled.success:
        return [*seen, *health.hp_facts(ctx, target.id, amount, sign=-1)]
    if save.on_success != "half":
        # `other` is a spell-specific consequence, which stays with the description.
        return seen
    # No dice expression can express half of itself, so the roll lands and the total is halved.
    total, halving = rolls.roll_dice(amount, ctx.rng)
    return [*seen, halving, *health.hp_facts(ctx, target.id, total // 2, sign=-1)]
