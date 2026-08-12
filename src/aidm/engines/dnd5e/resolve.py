from collections.abc import Mapping
from random import Random

from pydantic import JsonValue

from aidm.engines.counters import adjust, spend
from aidm.state.apply import apply_effect, require_actor_here
from aidm.state.base import Entity, Slug
from aidm.state.dice import roll
from aidm.state.effects import Reveal
from aidm.state.facts import Fact
from aidm.state.packs import Content, ContentMiss, ContentRef, Record, parse_ref
from aidm.state.world import GameState

from .actions import Action, Attack, CastSpell, Check, Improvise, Rest, UseFeature
from .content import lookup
from .mechanics import (
    Mechanics,
    counter_of,
    first_ref_record,
    modifier,
    read,
    refill,
    set_note,
    sheet_of,
    write,
)

SUCCESS: Slug = "success"
FAILURE: Slug = "failure"
AIMED = "{spell} is aimed at a creature: name its `target_id`"

type Resolved = tuple[list[Fact], Slug | None]


def dispatch_action(
    content: Content, draft: GameState, action: Action | None, rng: Random
) -> Resolved:
    """The plan union is the action registry: one arm per member, exhaustively."""
    if action is None:
        return [], None
    mechanics = read(draft)
    match action:
        case Attack():
            result = resolve_attack(content, draft, action, rng, mechanics)
        case CastSpell():
            result = resolve_cast_spell(content, draft, action, rng, mechanics)
        case Check():
            result = resolve_check(content, draft, action, rng, mechanics)
        case UseFeature():
            result = resolve_use_feature(content, draft, action, rng, mechanics)
        case Rest():
            result = resolve_rest(content, draft, action, rng, mechanics)
        case Improvise():
            result = resolve_improvise(content, draft, action, rng, mechanics)
    write(draft, mechanics)
    return result


def resolve_check(
    content: Content, draft: GameState, action: Check, rng: Random, mechanics: Mechanics
) -> Resolved:
    del content, mechanics
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    rolled, fact = roll(
        "1d20",
        f"{actor.name}: {action.reason}",
        rng,
        vs=action.dc,
        mode=action.mode,
        bonus=action.bonus,
    )
    facts.append(fact)
    return facts, SUCCESS if rolled.total >= action.dc else FAILURE


def resolve_rest(
    content: Content, draft: GameState, action: Rest, rng: Random, mechanics: Mechanics
) -> Resolved:
    del content, rng
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    recharges = ("short-rest",) if action.label == "short-rest" else ("short-rest", "long-rest")
    facts.extend(refill(actor, sheet_of(mechanics, actor), action.label, recharges))
    return facts, None


def resolve_use_feature(
    content: Content, draft: GameState, action: UseFeature, rng: Random, mechanics: Mechanics
) -> Resolved:
    del content
    actor = require_actor_here(draft, action.actor_id)
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    sheet = sheet_of(mechanics, actor)
    facts.extend(spend(actor, action.counter, counter_of(sheet, actor, action.counter), 1, ""))
    if action.heal is not None:
        rolled, fact = roll(action.heal, f"{actor.name} draws on {action.counter}", rng)
        facts.append(fact)
        facts.extend(
            adjust(actor, "hp", counter_of(sheet, actor, "hp"), rolled.total, action.counter)
        )
    return facts, None


def resolve_improvise(
    content: Content, draft: GameState, action: Improvise, rng: Random, mechanics: Mechanics
) -> Resolved:
    del content, draft, mechanics
    rolled, fact = roll(action.dice, action.reason, rng, vs=action.vs, mode=action.mode)
    if action.vs is None:
        return [fact], None
    return [fact], SUCCESS if rolled.total >= action.vs else FAILURE


def resolve_attack(
    content: Content, draft: GameState, action: Attack, rng: Random, mechanics: Mechanics
) -> Resolved:
    actor = require_actor_here(draft, action.actor_id)
    target = require_actor_here(draft, action.target_id)
    weapon = (
        None
        if action.weapon_item_id is None
        else draft.world.require_kind(action.weapon_item_id, "item")
    )
    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    facts.extend(apply_effect(draft, Reveal(entity_id=action.target_id)))

    if weapon is None:
        if action.attack_bonus is None or action.damage is None:
            raise ValueError(
                "an attack needs either a `weapon_item_id` the attacker carries, or both "
                "`attack_bonus` and `damage` copied off their stat block's attack line"
            )
    else:
        if action.attack_bonus is not None or action.damage is not None:
            raise ValueError(
                "a weapon's to-hit and damage come from its record: leave `attack_bonus` and "
                "`damage` null when you name a `weapon_item_id`"
            )
        if weapon.parent_id != actor.id:
            raise ValueError(f"{actor.name} does not carry item '{action.weapon_item_id}'")

    weapon_facts: Mapping[Slug, JsonValue] = {}
    if weapon is not None:
        record = first_ref_record(sheet_of(mechanics, weapon), content, "weapons", "damage")
        if record is None:
            raise ValueError(
                f"{weapon.name} is no weapon. Attack with a weapon the attacker carries, or "
                "give `attack_bonus` and `damage` yourself."
            )
        weapon_facts = record.facts

    strength_mod = ability_modifier(mechanics, actor, "strength")
    dexterity_mod = ability_modifier(mechanics, actor, "dexterity")
    reach_mod = dexterity_mod if weapon_facts.get("ranged") else strength_mod
    weapon_mod = max(strength_mod, dexterity_mod) if weapon_facts.get("finesse") else reach_mod

    to_hit, damage_dice, damage_bonus = action.attack_bonus, action.damage, 0
    if weapon is not None:
        versatile = weapon_facts.get("versatile-damage")
        wielded = versatile if action.two_handed and versatile is not None else None
        to_hit = weapon_mod + sheet_of(mechanics, actor).numbers.get("proficiency-bonus", 0)
        damage_dice = _dice(weapon_facts["damage"] if wielded is None else wielded)
        damage_bonus = weapon_mod
    assert to_hit is not None and damage_dice is not None  # the refusals above guarantee both

    armor_class = _number(mechanics, target, "armor-class")
    rolled, fact = roll(
        "1d20",
        f"{actor.name} attacks {target.name}",
        rng,
        vs=armor_class,
        mode=action.mode,
        bonus=to_hit,
    )
    facts.append(fact)
    if rolled.total < armor_class:
        return facts, FAILURE

    hurt, damage_fact = roll(damage_dice, f"{actor.name}'s damage", rng, bonus=damage_bonus)
    facts.append(damage_fact)
    facts.extend(
        adjust(
            target,
            "hp",
            counter_of(sheet_of(mechanics, target), target, "hp"),
            -hurt.total,
            f"{actor.name}'s attack",
        )
    )
    return facts, SUCCESS


def resolve_cast_spell(
    content: Content, draft: GameState, action: CastSpell, rng: Random, mechanics: Mechanics
) -> Resolved:
    actor = require_actor_here(draft, action.actor_id)
    target = None if action.target_id is None else require_actor_here(draft, action.target_id)

    ref, spell = spell_of(content, action.spell)
    klass = first_ref_record(
        sheet_of(mechanics, actor), content, "classes", require_fact="spellcasting"
    )
    if ref not in sheet_of(mechanics, actor).refs:
        if klass is None:
            raise ValueError(
                "this actor's class casts no spells, so it has no spellcasting ability: resolve "
                "what they do with `improvise` instead"
            )
        raise ValueError(
            f"{actor.name} does not know {spell.name}: cast a spell their own `content` lists, "
            "or resolve what they do with `improvise` instead"
        )
    # A racial cantrip comes without a casting class — the high elf's is cast off Intelligence.
    casting = "intelligence" if klass is None else _ability(klass.facts.get("spellcasting"))
    mod = ability_modifier(mechanics, actor, casting)

    level = spell.facts.get("level")
    if level is None and action.slot_level is not None:
        raise ValueError(f"{spell.name} is a cantrip: it spends no slot, so leave it null")
    if level is not None and action.slot_level is None:
        raise ValueError(
            f"{spell.name} is a level {level} spell: name the `slot_level` it is cast from"
        )
    if level is not None and action.slot_level is not None and action.slot_level < _whole(level):
        raise ValueError(
            f"{spell.name} needs a slot of level {level} or higher, not {action.slot_level}"
        )

    facts = apply_effect(draft, Reveal(entity_id=action.actor_id))
    if action.target_id is not None:
        facts.extend(apply_effect(draft, Reveal(entity_id=action.target_id)))
    if action.slot_level is not None:
        sheet = sheet_of(mechanics, actor)
        key = f"slot-{action.slot_level}"
        facts.extend(spend(actor, key, counter_of(sheet, actor, key), 1, ""))

    attack_type = spell.facts.get("attack-type")
    save_ability = spell.facts.get("save-ability")
    proficiency = sheet_of(mechanics, actor).numbers.get("proficiency-bonus", 0)
    outcome: Slug | None = None

    if attack_type is not None:
        if target is None:
            raise ValueError(AIMED.format(spell=spell.name))
        spell_ac = _number(mechanics, target, "armor-class")
        rolled, fact = roll(
            "1d20",
            f"{actor.name} casts {spell.name} at {target.name}",
            rng,
            vs=spell_ac,
            bonus=mod + proficiency,
        )
        facts.append(fact)
        outcome = SUCCESS if rolled.total >= spell_ac else FAILURE

    dc = 8 + proficiency + mod
    if attack_type is None and save_ability is not None:
        if target is None:
            raise ValueError(AIMED.format(spell=spell.name))
        save_bonus = ability_modifier(mechanics, target, _ability(save_ability))
        rolled, fact = roll(
            "1d20", f"{target.name} resists {spell.name}", rng, vs=dc, bonus=save_bonus
        )
        facts.append(fact)
        outcome = FAILURE if rolled.total >= dc else SUCCESS

    scale = (
        action.slot_level
        if action.slot_level is not None
        else sheet_of(mechanics, actor).numbers.get("level", 1)
    )
    # A saved target takes half only where the spell says so; otherwise the spell does nothing.
    lands = spell.facts.get("save-success") == "half" if outcome == FAILURE else True
    halver = 2 if outcome == FAILURE else 1

    damage_dice = ladder_pick(spell.facts.get("damage-ladder"), scale, "damage-ladder")
    if damage_dice is not None and lands:
        if action.target_id is None or target is None:
            raise ValueError(AIMED.format(spell=spell.name))
        dealt, fact = roll(
            _dice(damage_dice),
            f"{spell.name} damage",
            rng,
            bonus=mod if spell.facts.get("damage-with-modifier") else 0,
        )
        facts.append(fact)
        facts.extend(
            adjust(
                target,
                "hp",
                counter_of(sheet_of(mechanics, target), target, "hp"),
                -(dealt.total // halver),
                spell.name,
            )
        )

    heal_dice = ladder_pick(spell.facts.get("heal-ladder"), scale, "heal-ladder")
    if heal_dice is not None and lands:
        healed_target = target if target is not None else actor
        healed, fact = roll(
            _dice(heal_dice),
            f"{spell.name} healing",
            rng,
            bonus=mod if spell.facts.get("heal-with-modifier") else 0,
        )
        facts.append(fact)
        facts.extend(
            adjust(
                healed_target,
                "hp",
                counter_of(sheet_of(mechanics, healed_target), healed_target, "hp"),
                healed.total,
                spell.name,
            )
        )

    if spell.facts.get("concentration"):
        facts.extend(set_note(actor, sheet_of(mechanics, actor), "concentration", spell.name))
    return facts, outcome


def spell_of(content: Content, ref: str) -> tuple[ContentRef, Record]:
    reference = parse_ref(ref)
    if reference.collection != "spells":
        raise ValueError(f"'{ref}' names no spell: name a record from the spells collection")
    found = lookup(content, reference)
    if found is None:
        miss = content.record(reference)
        assert isinstance(miss, ContentMiss)  # engine.record returned None for the same lookup
        raise ValueError(f"{miss.summary}; use a ref exactly as it was shown")
    return reference, found


def ladder_pick(rows: JsonValue, at: int, fact: str) -> JsonValue:
    """The last `[threshold, value]` row at or below `at`; an absent fact or no reach is null."""
    if rows is None:
        return None
    if not isinstance(rows, list):
        raise ValueError(f"fact {fact!r} holds {rows!r}, which is no ladder")
    best: int | None = None
    picked: JsonValue = None
    for row in rows:
        match row:
            case [int() as threshold, value] if not isinstance(threshold, bool):
                if threshold <= at and (best is None or threshold >= best):
                    best, picked = threshold, value
            case _:
                raise ValueError(f"fact {fact!r} row {row!r} is no [threshold, value] pair")
    return picked


def ability_modifier(mechanics: Mechanics, entity: Entity, ability: str) -> int:
    return modifier(_number(mechanics, entity, ability))


def _number(mechanics: Mechanics, entity: Entity, key: str) -> int:
    numbers = sheet_of(mechanics, entity).numbers
    if key not in numbers:
        raise ValueError(f"{entity.name} has no {key!r} on their sheet")
    return numbers[key]


def _ability(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is no ability to read off a sheet")
    return value


def _whole(value: JsonValue) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{value!r} is no whole number")
    return value


def _dice(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{value!r} is no dice expression")
    return value
